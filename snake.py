"""
V8 - Cuộn thích ứng theo đường ra
- Đường ra ở trên/dưới -> cuộn trái-phải
- Đường ra ở trái/phải -> cuộn lên-xuống
- Táo random 100%, Tier ưu tiên Ăn > Sống > Rộng + Sát tường + Chừa đường
"""
import pygame, heapq, random
from collections import deque

CELL_SIZE=22
GRID_W,GRID_H=32,24
WIDTH,HEIGHT=GRID_W*CELL_SIZE, GRID_H*CELL_SIZE
BASE_FPS=15

BG=(14,14,18)
GRID_COLOR=(28,28,32)
SNAKE_COL=(90,230,120)
HEAD_COL=(140,255,170)
FOOD_COL=(255,70,70)
BRICK_COL=(110,110,125)
CORRIDOR_COL=(60,80,120)

GHOST_COLS={
    'will_eat':(80,220,255),
    'safe':(255,230,80),
    'trap_after_eat':(255,140,50),
    'risky':(160,160,160),
    'dead':(255,60,60),
    'enclosure':(255,50,255),
    'loop_break':(255,100,255),
}

DIRS={'UP':(0,-1),'DOWN':(0,1),'LEFT':(-1,0),'RIGHT':(1,0)}
DIR_LIST=list(DIRS.values())
OPPOSITE={DIRS['UP']:DIRS['DOWN'],DIRS['DOWN']:DIRS['UP'],DIRS['LEFT']:DIRS['RIGHT'],DIRS['RIGHT']:DIRS['LEFT']}
LEFT_TURN={DIRS['UP']:DIRS['LEFT'],DIRS['LEFT']:DIRS['DOWN'],DIRS['DOWN']:DIRS['RIGHT'],DIRS['RIGHT']:DIRS['UP']}
RIGHT_TURN={DIRS['UP']:DIRS['RIGHT'],DIRS['RIGHT']:DIRS['DOWN'],DIRS['DOWN']:DIRS['LEFT'],DIRS['LEFT']:DIRS['UP']}

def manhattan(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])
def get_corridor(w,h):
    s=set()
    for x in range(w):
        s.add((x,1)); s.add((x,h-2))
    for y in range(1,h-1):
        s.add((1,y)); s.add((w-2,y))
    return s
CORRIDOR=get_corridor(GRID_W,GRID_H)

def flood_fill(start, obstacles, w,h):
    if start in obstacles: return 0,set()
    q=deque([start]); vis={start}
    while q:
        cur=q.popleft()
        for dx,dy in DIR_LIST:
            nx,ny=cur[0]+dx,cur[1]+dy
            nxt=(nx,ny)
            if 0<=nx<w and 0<=ny<h and nxt not in obstacles and nxt not in vis:
                vis.add(nxt); q.append(nxt)
    return len(vis), vis

def total_free(snake_set,bricks,w,h):
    return w*h - len(snake_set) - len(bricks)

def wall_hug_score(pos, bricks, w,h):
    x,y=pos; s=0
    if x<=1 or x>=w-2 or y<=1 or y>=h-2: s+=3
    if x==0 or x==w-1 or y==0 or y==h-1: s+=5
    for dx,dy in DIR_LIST:
        nx,ny=x+dx,y+dy
        if not (0<=nx<w and 0<=ny<h): s+=2
        elif (nx,ny) in bricks: s+=2
    return s

def get_exit_dir(head, food, reach_set, w,h):
    """Tìm hướng đường ra: táo ở đâu hoặc vùng trống lớn ở đâu"""
    # Ưu tiên hướng tới táo nếu táo trong reach
    if food in reach_set:
        dx=food[0]-head[0]
        dy=food[1]-head[1]
        # hướng chính
        if abs(dx) > abs(dy):
            return DIRS['RIGHT'] if dx>0 else DIRS['LEFT']
        else:
            return DIRS['DOWN'] if dy>0 else DIRS['UP']
    # Nếu táo không trong reach, tìm hướng vùng trống lớn nhất
    # đếm số ô trống theo 4 hướng
    counts={}
    for d in DIR_LIST:
        cnt=0
        for p in reach_set:
            if d==DIRS['UP'] and p[1] < head[1]: cnt+=1
            elif d==DIRS['DOWN'] and p[1] > head[1]: cnt+=1
            elif d==DIRS['LEFT'] and p[0] < head[0]: cnt+=1
            elif d==DIRS['RIGHT'] and p[0] > head[0]: cnt+=1
        counts[d]=cnt
    return max(counts, key=counts.get) if counts else DIRS['UP']

def a_star(start, goal, obstacles, w,h, start_dir, turn_penalty=0):
    if start==goal: return [start],0
    if goal in obstacles: return None
    heap=[(manhattan(start,goal),0,start,start_dir,[start],0)]
    best={}
    while heap:
        f,g,pos,prev_dir,path,turns=heapq.heappop(heap)
        key=(pos,prev_dir)
        if key in best and best[key]<=g: continue
        best[key]=g
        if pos==goal: return path,turns
        for nd in DIR_LIST:
            if nd==OPPOSITE.get(prev_dir) and len(path)>1: continue
            nx,ny=pos[0]+nd[0],pos[1]+nd[1]
            npos=(nx,ny)
            if not (0<=nx<w and 0<=ny<h): continue
            if npos in obstacles: continue
            is_turn=0 if nd==prev_dir else 1
            ng=g+1+(turn_penalty if is_turn else 0)
            nturns=turns+is_turn
            nf=ng+manhattan(npos,goal)
            heapq.heappush(heap,(nf,ng,npos,nd,path+[npos],nturns))
    return None

def evaluate_ghost(snake,food,bricks,initial_dir,cur_dir,w,h, recent_set):
    head=snake[0]
    new_head=(head[0]+initial_dir[0], head[1]+initial_dir[1])
    snake_set=set(snake)
    if not (0<=new_head[0]<w and 0<=new_head[1]<h):
        return {'dir':initial_dir,'status':'dead','score':-10000,'path':[new_head],'turns':99,'flood':0,'edge':0,'wall':0,'len':99,'exit_dir':None,'reason':'wall'}
    if new_head in (snake_set - {snake[-1]}) or new_head in bricks:
        return {'dir':initial_dir,'status':'dead','score':-10000,'path':[new_head],'turns':99,'flood':0,'edge':0,'wall':0,'len':99,'exit_dir':None,'reason':'hit'}

    new_snake_tmp=[new_head]+snake[:-1] if new_head!=food else [new_head]+snake
    obstacles=(set(new_snake_tmp)-{new_head})|bricks
    flood_area, reach_set = flood_fill(new_head, obstacles, w,h)
    tot=total_free(set(new_snake_tmp),bricks,w,h)
    connected=(flood_area-1==tot)
    free_corr=CORRIDOR - set(new_snake_tmp) - bricks
    edge_reach=len(free_corr & reach_set)
    wall_hug=wall_hug_score(new_head, bricks, w,h)
    loop_pen=2500 if new_head in recent_set else 0
    small=flood_area < 60
    exit_dir=get_exit_dir(new_head, food, reach_set, w,h)

    # Bonus cuộn vuông góc với đường ra
    # Nếu đường ra ở trên/dưới (vertical) -> ưu tiên cuộn trái/phải (horizontal)
    # Nếu đường ra ở trái/phải (horizontal) -> ưu tiên cuộn lên/xuống (vertical)
    coil_bonus=0
    if exit_dir in (DIRS['UP'], DIRS['DOWN']):
        # đường ra dọc -> cuộn ngang
        if initial_dir in (DIRS['LEFT'], DIRS['RIGHT']):
            coil_bonus=800
    else:
        # đường ra ngang -> cuộn dọc
        if initial_dir in (DIRS['UP'], DIRS['DOWN']):
            coil_bonus=800

    if new_head==food:
        sc=10000 + flood_area*0.2 + wall_hug*2 + coil_bonus - loop_pen - (1000 if small else 0)
        return {'dir':initial_dir,'status':'will_eat','score':sc,'path':[new_head],'turns':0,'flood':flood_area,'edge':edge_reach,'wall':wall_hug,'len':1,'connected':connected,'exit_dir':exit_dir,'coil_bonus':coil_bonus,'reason':f'EAT exit:{exit_dir} coil:{coil_bonus} f:{flood_area}'}

    obs_food=(set(new_snake_tmp[1:-1])|bricks) if len(new_snake_tmp)>2 else bricks
    turn_pen=0 if len(snake)<25 else 4
    res=a_star(new_head, food, obs_food, w,h, initial_dir, turn_penalty=turn_pen)
    if res:
        path,turns=res
        food_in_reach=food in reach_set
        if not food_in_reach:
            sc= -5000 + flood_area*0.3 - len(path)*10 - loop_pen + coil_bonus*0.5
            return {'dir':initial_dir,'status':'enclosure','score':sc,'path':path,'turns':turns,'flood':flood_area,'edge':edge_reach,'wall':wall_hug,'len':len(path),'connected':connected,'exit_dir':exit_dir,'coil_bonus':coil_bonus,'reason':f'no food f:{flood_area}'}
        sc=10000 - len(path)*80 - turns*2 + flood_area*0.1 + wall_hug*1 + coil_bonus - loop_pen - (800 if small else 0)
        status='will_eat' if not small else 'enclosure'
        return {'dir':initial_dir,'status':status,'score':sc,'path':path,'turns':turns,'flood':flood_area,'edge':edge_reach,'wall':wall_hug,'len':len(path),'connected':connected,'exit_dir':exit_dir,'coil_bonus':coil_bonus,'reason':f'EAT {len(path)}s exit:{exit_dir} coil:{coil_bonus}'}

    obs_tail=(set(new_snake_tmp[1:-1])|bricks) if len(new_snake_tmp)>2 else bricks
    res_tail=a_star(new_head, new_snake_tmp[-1], obs_tail, w,h, initial_dir, turn_penalty=turn_pen)
    if res_tail:
        path_tail,turns_tail=res_tail
        sc=flood_area*0.6 + edge_reach*10 + wall_hug*8 + coil_bonus*1.2 - turns_tail*3 - loop_pen + (1000 if connected else -800) - (1000 if small else 0)
        status='safe' if not small else 'enclosure'
        return {'dir':initial_dir,'status':status,'score':sc,'path':path_tail,'turns':turns_tail,'flood':flood_area,'edge':edge_reach,'wall':wall_hug,'len':len(path_tail),'connected':connected,'exit_dir':exit_dir,'coil_bonus':coil_bonus,'reason':f'SAFE exit:{exit_dir} coil:{coil_bonus} f:{flood_area}'}
    return {'dir':initial_dir,'status':'risky','score':flood_area*0.2 + coil_bonus -200 - loop_pen,'path':[new_head],'turns':0,'flood':flood_area,'edge':edge_reach,'wall':wall_hug,'len':99,'connected':connected,'exit_dir':exit_dir,'coil_bonus':coil_bonus,'reason':f'RISKY'}

def random_food(snake,bricks,w,h):
    s=set(snake)|bricks
    free=[(x,y) for x in range(w) for y in range(h) if (x,y) not in s]
    return random.choice(free) if free else (random.randint(0,w-1),random.randint(0,h-1))

def draw_cell(screen,pos,color,alpha=255,border=6):
    x,y=pos[0]*CELL_SIZE,pos[1]*CELL_SIZE
    if alpha<255:
        surf=pygame.Surface((CELL_SIZE-2,CELL_SIZE-2),pygame.SRCALPHA)
        surf.fill((*color,alpha))
        screen.blit(surf,(x+1,y+1))
    else:
        pygame.draw.rect(screen,color,(x+1,y+1,CELL_SIZE-2,CELL_SIZE-2),border_radius=border)

def dir_name(d):
    return {DIRS['UP']:'UP',DIRS['DOWN']:'DN',DIRS['LEFT']:'LT',DIRS['RIGHT']:'RT'}.get(d,'?')

def main():
    pygame.init()
    font=pygame.font.SysFont("monospace",10)
    big=pygame.font.SysFont("monospace",18,bold=True)
    screen=pygame.display.set_mode((WIDTH,HEIGHT))
    clock=pygame.time.Clock()

    snake=[(GRID_W//2,GRID_H//2),(GRID_W//2-1,GRID_H//2),(GRID_W//2-2,GRID_H//2)]
    cur_dir=DIRS['RIGHT']
    bricks=set()
    food=random_food(snake,bricks,GRID_W,GRID_H)
    score=0
    build_mode=False; game_over=False; paused=False; speed=1
    ghosts=[]; ghosts_sorted=[]
    pos_history=deque(maxlen=30)

    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); return
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: pygame.quit(); return
                if ev.key==pygame.K_b: build_mode=not build_mode; paused=build_mode
                if ev.key==pygame.K_c: bricks.clear()
                if ev.key==pygame.K_r:
                    snake=[(GRID_W//2,GRID_H//2),(GRID_W//2-1,GRID_H//2),(GRID_W//2-2,GRID_H//2)]
                    cur_dir=DIRS['RIGHT']; food=random_food(snake,bricks,GRID_W,GRID_H); score=0; game_over=False; paused=False; pos_history.clear()
                if ev.key==pygame.K_p: paused=not paused
                if ev.key==pygame.K_f: speed=20 if speed==1 else 1
                if ev.key in (pygame.K_EQUALS, pygame.K_PLUS): speed=min(100,speed+1)
                if ev.key==pygame.K_MINUS: speed=max(1,speed-1)
            if ev.type==pygame.MOUSEBUTTONDOWN and build_mode:
                gx,gy=ev.pos[0]//CELL_SIZE, ev.pos[1]//CELL_SIZE
                pos=(gx,gy)
                if 0<=gx<GRID_W and 0<=gy<GRID_H and pos not in snake and pos!=food:
                    if ev.button==1: bricks.add(pos)
                    elif ev.button==3: bricks.discard(pos)
            if ev.type==pygame.MOUSEMOTION and build_mode:
                if pygame.mouse.get_pressed()[0]:
                    gx,gy=ev.pos[0]//CELL_SIZE, ev.pos[1]//CELL_SIZE
                    pos=(gx,gy)
                    if 0<=gx<GRID_W and 0<=gy<GRID_H and pos not in snake and pos!=food:
                        bricks.add(pos)
                if pygame.mouse.get_pressed()[2]:
                    gx,gy=ev.pos[0]//CELL_SIZE, ev.pos[1]//CELL_SIZE
                    bricks.discard((gx,gy))

        keys=pygame.key.get_pressed()
        cur_speed=40 if (keys[pygame.K_SPACE] and not build_mode) else speed
        render_fps=BASE_FPS*cur_speed if cur_speed<=10 else BASE_FPS*10
        logic_steps=1 if cur_speed<=10 else max(1,cur_speed//8)

        if not build_mode and not paused and not game_over:
            for _ in range(logic_steps):
                head=snake[0]
                recent_set=set(pos_history)
                is_looping = list(pos_history).count(head) >= 4

                forced=None
                for dvec in DIR_LIST:
                    nh=(head[0]+dvec[0], head[1]+dvec[1])
                    if nh==food and nh not in (set(snake)-{snake[-1]}) and nh not in bricks:
                        forced=dvec; break
                if forced is not None:
                    cur_dir=forced
                else:
                    candidates=[cur_dir, LEFT_TURN[cur_dir], RIGHT_TURN[cur_dir]]
                    candidates=[d for d in candidates if d!=OPPOSITE[cur_dir]]
                    ghosts=[]
                    for init_dir in candidates:
                        g=evaluate_ghost(snake,food,bricks,init_dir,cur_dir,GRID_W,GRID_H, recent_set)
                        ghosts.append(g)
                    alive=[g for g in ghosts if g['status']!='dead']
                    if not alive:
                        game_over=True; break

                    will_eat=[g for g in alive if 'will_eat' in g['status']]
                    safe=[g for g in alive if g['status']=='safe']
                    enclosure=[g for g in alive if 'enclosure' in g['status']]
                    risky=[g for g in alive if g['status']=='risky']

                    if is_looping:
                        other=[g for g in alive if g['dir']!=cur_dir]
                        if other:
                            ghosts_sorted=sorted(other,key=lambda x:(x['flood'], x['score']),reverse=True)
                            for g in ghosts_sorted: g['status']='loop_break'
                        else:
                            ghosts_sorted=alive
                    elif will_eat:
                        wide_eat=[g for g in will_eat if g['flood']>=60]
                        pool=wide_eat if wide_eat else will_eat
                        ghosts_sorted=sorted(pool,key=lambda x:(x['len'], -x['flood']))
                    elif safe:
                        # Ưu tiên cuộn vuông góc với đường ra + rộng + sát tường
                        ghosts_sorted=sorted(safe,key=lambda x:( -x['coil_bonus'], -x['flood'], -x['wall'], -int(x['connected'])))
                    else:
                        pool=enclosure+risky
                        ghosts_sorted=sorted(pool,key=lambda x:( -x['flood'], -x['wall']))

                    if ghosts_sorted:
                        cur_dir=ghosts_sorted[0]['dir']
                        ghosts=ghosts_sorted

                new_head=(snake[0][0]+cur_dir[0], snake[0][1]+cur_dir[1])
                if not (0<=new_head[0]<GRID_W and 0<=new_head[1]<GRID_H) or new_head in set(snake[:-1]) or new_head in bricks:
                    game_over=True; break
                pos_history.append(new_head)
                if new_head==food:
                    snake=[new_head]+snake; score+=1
                    food=random_food(snake,bricks,GRID_W,GRID_H)
                else:
                    snake=[new_head]+snake[:-1]
        elif build_mode:
            candidates=[cur_dir, LEFT_TURN[cur_dir], RIGHT_TURN[cur_dir]]
            candidates=[d for d in candidates if d!=OPPOSITE[cur_dir]]
            ghosts=[]
            for init_dir in candidates:
                g=evaluate_ghost(snake,food,bricks,init_dir,cur_dir,GRID_W,GRID_H, set(pos_history))
                ghosts.append(g)
            ghosts_sorted=sorted([g for g in ghosts if g['status']!='dead'],key=lambda x:x['score'],reverse=True)

        screen.fill(BG)
        for x in range(GRID_W):
            pygame.draw.line(screen,GRID_COLOR,(x*CELL_SIZE,0),(x*CELL_SIZE,HEIGHT),1)
        for y in range(GRID_H):
            pygame.draw.line(screen,GRID_COLOR,(0,y*CELL_SIZE),(WIDTH,y*CELL_SIZE),1)
        for c in CORRIDOR:
            if c not in bricks:
                draw_cell(screen,c,CORRIDOR_COL,alpha=10,border=2)
        for b in bricks:
            draw_cell(screen,b,BRICK_COL,border=3)
        for g in sorted(ghosts_sorted if 'ghosts_sorted' in locals() else ghosts, key=lambda x:x['score']):
            col=GHOST_COLS.get(g['status'],(100,100,100))
            for i,pos in enumerate(g['path']):
                if pos in snake or pos in bricks: continue
                alpha=max(18, 150 - i*4)
                draw_cell(screen,pos,col,alpha=alpha,border=4)

        draw_cell(screen,food,FOOD_COL,border=10)
        for i,pos in enumerate(snake):
            draw_cell(screen,pos, HEAD_COL if i==0 else SNAKE_COL, border=7 if i==0 else 5)

        best=ghosts_sorted[0] if ghosts_sorted else {}
        tier="EAT" if 'will_eat' in best.get('status','') else ("SAFE" if best.get('status')=='safe' else "ENC")
        exit_txt=dir_name(best.get('exit_dir')) if best.get('exit_dir') else "?"
        coil_txt="LR" if best.get('exit_dir') in (DIRS['UP'],DIRS['DOWN']) else "UD" if best.get('exit_dir') else "?"
        txt=font.render(f"Sc:{score} {tier} Exit:{exit_txt} Coil:{coil_txt} {best.get('reason','')} Spd:x{cur_speed}",True,(230,230,230))
        screen.blit(txt,(4,4))
        if ghosts_sorted:
            y=14
            for g in ghosts_sorted[:3]:
                line=f"{dir_name(g['dir'])} {g['status']} len:{g['len']} f:{g['flood']} coil:{g['coil_bonus']} sc:{int(g['score'])}"
                t=font.render(line,True,GHOST_COLS.get(g['status'],(200,200,200)))
                screen.blit(t,(4,y)); y+=10
        if game_over:
            over=big.render(f"GAME OVER Score:{score} - R reset",True,(255,120,120))
            screen.blit(over,(WIDTH//2-over.get_width()//2,HEIGHT//2))
        pygame.display.flip()
        clock.tick(render_fps if not build_mode else 30)

if __name__=="__main__":
    main()
