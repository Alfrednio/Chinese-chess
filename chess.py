import pygame
import sys
import subprocess
import time
import os

pygame.init()

# ==============================
# 【修改1】缩小棋盘格子尺寸（原75→60，可根据需要调整）
# 同时适配窗口边距，避免显示不全
# ==============================
GRID_SIZE = 60  # 原75，减小格子尺寸后整体棋盘会缩小
BOARD_COL = 9
BOARD_ROW = 10
# 【修改2】调整窗口宽高计算（基于新的GRID_SIZE，边距保留少量冗余避免裁切）
WINDOW_W = BOARD_COL * GRID_SIZE + 60  # 原+20，保留更多右侧边距
WINDOW_H = BOARD_ROW * GRID_SIZE + 80  # 原+40，保留更多底部边距
START_X = 40  # 原10，增加左侧边距（避免棋盘左边缘裁切）
START_Y = 40  # 原10，增加上侧边距（避免棋盘上边缘裁切）

screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
pygame.display.set_caption("中国象棋 - AI自动走棋 (修复版)")

BOARD_BG = (229, 194, 159)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
WHITE = (255, 255, 255)
HIGHLIGHT = (100, 200, 100)
LINE = (0, 0, 0)

try:
    font_big = pygame.font.SysFont(["SimHei", "Microsoft YaHei"], 34)
    font_small = pygame.font.SysFont(["SimHei", "Microsoft YaHei"], 16)
except:
    font_big = pygame.font.Font(None, 34)
    font_small = pygame.font.Font(None, 16)

# 棋子初始化数据
PIECE_DATA = [
    (0,0,'车',BLACK,'b_rook1'), (1,0,'马',BLACK,'b_elephant1'), (2,0,'象',BLACK,'b_guard1'), (3,0,'士',BLACK,'b_king'),
    (4,0,'将',BLACK,'b_horse1'), (5,0,'士',BLACK,'b_guard2'), (6,0,'象',BLACK,'b_elephant2'), (7,0,'马',BLACK,'b_horse2'), (8,0,'车',BLACK,'b_rook2'),
    (1,2,'炮',BLACK,'b_cannon1'), (7,2,'炮',BLACK,'b_cannon2'),
    (0,3,'卒',BLACK,'b_pawn1'), (2,3,'卒',BLACK,'b_pawn2'), (4,3,'卒',BLACK,'b_pawn3'), (6,3,'卒',BLACK,'b_pawn4'), (8,3,'卒',BLACK,'b_pawn5'),

    (0,9,'車',RED,'r_rook1'), (1,9,'馬',RED,'r_horse1'), (2,9,'相',RED,'r_elephant1'), (3,9,'仕',RED,'r_guard1'),
    (4,9,'帅',RED,'r_king'), (5,9,'仕',RED,'r_guard2'), (6,9,'相',RED,'r_elephant2'), (7,9,'馬',RED,'r_horse2'), (8,9,'車',RED,'r_rook2'),
    (1,7,'炮',RED,'r_cannon1'), (7,7,'炮',RED,'r_cannon2'),
    (0,6,'兵',RED,'r_pawn1'), (2,6,'兵',RED,'r_pawn2'), (4,6,'兵',RED,'r_pawn3'), (6,6,'兵',RED,'r_pawn4'), (8,6,'兵',RED,'r_pawn5'),
]

pieces = {p[4]: list(p[:4]) for p in PIECE_DATA}
move_history = [] # 【新增】记录走棋步骤，例如 ['b2e2', 'h9g7']

# ==============================
# 核心：坐标转换修复
# UCI标准：x(a-i), y(0-9, 0是底部/红方底线)
# Pygame：x(0-8), y(0-9, 0是顶部/黑方底线)
# ==============================

def xy_to_uci(c, r):
    """ 将屏幕坐标 (col, row) 转换为 UCI 字符串 (如 'e2') """
    uci_file = chr(ord('a') + c) # 0->a, 1->b
    uci_rank = str(9 - r)        # 9->0, 8->1 (屏幕y向下增大，UCI y向上增大)
    return f"{uci_file}{uci_rank}"

def uci_to_pos(uci):
    """ 将 UCI 字符串 (如 'e2') 转换为屏幕坐标 (col, row) """
    try:
        if not uci: return None
        file_char = uci[0]
        rank_char = uci[1]
        
        col = ord(file_char) - ord('a')
        row = 9 - int(rank_char) # 转换回屏幕坐标
        return col, row
    except:
        return None

def apply_move_logic(fcol, frow, tcol, trow):
    """ 执行移动逻辑（无论是AI还是玩家） """
    # 1. 找到被吃掉的棋子
    target_pid = None
    for pid, v in pieces.items():
        pc, pr, _, _ = v
        if pc == tcol and pr == trow:
            target_pid = pid
            break
    
    # 2. 找到移动的棋子
    mover_pid = None
    for pid, v in pieces.items():
        pc, pr, _, _ = v
        if pc == fcol and pr == frow:
            mover_pid = pid
            break
            
    if not mover_pid:
        return False

    # 3. 执行吃子和移动
    if target_pid:
        del pieces[target_pid] # 移除被吃掉的棋子
        
    pieces[mover_pid][0] = tcol
    pieces[mover_pid][1] = trow
    
    # 【重点】播放音效或打印，确认移动发生
    print(f"移动发生: ({fcol},{frow}) -> ({tcol},{trow})")
    return True

# ==============================
# Pikafish 引擎
# ==============================
class Engine:
    def __init__(self):
        self.p = None
        self.ok = False
        self.dir = os.path.dirname(os.path.abspath(__file__))
        self.start()

    def start(self):
        try:
            # 确保 pikafish.exe 在同一目录下
            exepath = os.path.join(self.dir, "pikafish.exe")
            self.p = subprocess.Popen(
                [exepath],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                cwd=self.dir
            )
            self.p.stdin.write("uci\n")
            self.p.stdin.flush()
            start = time.time()
            while time.time() - start < 3:
                line = self.p.stdout.readline()
                if "uciok" in line:
                    self.ok = True
                    print("✅ AI引擎连接成功")
                    return
        except Exception as e:
            print(f"❌ 引擎启动失败: {e}")
            self.ok = False

    def bestmove(self, history_moves):
        """ 发送整个棋局历史给AI，获取最佳着法 """
        if not self.ok:
            return None
        try:
            # 构建 moves 字符串
            moves_str = " ".join(history_moves)
            cmd = f"position startpos moves {moves_str}\n"
            print(f"发送给AI: {cmd.strip()}") # 调试用
            
            self.p.stdin.write(cmd)
            self.p.stdin.write("go depth 8\n") # 增加一点深度
            self.p.stdin.flush()
            
            while True:
                line = self.p.stdout.readline()
                if not line: break
                if "bestmove" in line:
                    # 格式通常是 "bestmove h2e2 ponder xxxx"
                    return line.split()[1]
        except Exception as e:
            print(f"AI计算出错: {e}")
            return None
        return None

# ==============================
# 绘图函数
# ==============================
def draw_board():
    screen.fill((245,240,230))
    # 【修改3】棋盘背景绘制基于新的START_X/START_Y/GRID_SIZE，无需额外修改（变量已联动）
    pygame.draw.rect(screen, BOARD_BG, (START_X, START_Y, BOARD_COL*GRID_SIZE, BOARD_ROW*GRID_SIZE))
    # 横线
    for r in range(10):
        y = START_Y + r*GRID_SIZE
        pygame.draw.line(screen, LINE, (START_X, y), (START_X+8*GRID_SIZE, y), 2)
    # 竖线
    for c in range(9):
        x = START_X + c*GRID_SIZE
        if c == 0 or c == 8:
            pygame.draw.line(screen, LINE, (x, START_Y), (x, START_Y+9*GRID_SIZE), 2)
        else:
            pygame.draw.line(screen, LINE, (x, START_Y), (x, START_Y+4*GRID_SIZE), 2)
            pygame.draw.line(screen, LINE, (x, START_Y+5*GRID_SIZE), (x, START_Y+9*GRID_SIZE), 2)
    
    # 楚河汉界 (简单文字示意)
    # 实际项目中这里通常绘制特殊的交叉线和文字

    # ==============================
    # 新增：绘制将帅九宫格交叉线
    # ==============================
    # 黑方（将）九宫格：行0-2，列3-5
    # 左上到右下对角线
    pygame.draw.line(screen, LINE, 
                     (START_X + 3*GRID_SIZE, START_Y + 0*GRID_SIZE), 
                     (START_X + 5*GRID_SIZE, START_Y + 2*GRID_SIZE), 2)
    # 右上到左下对角线
    pygame.draw.line(screen, LINE, 
                     (START_X + 5*GRID_SIZE, START_Y + 0*GRID_SIZE), 
                     (START_X + 3*GRID_SIZE, START_Y + 2*GRID_SIZE), 2)
    
    # 红方（帅）九宫格：行7-9，列3-5
    # 左上到右下对角线
    pygame.draw.line(screen, LINE, 
                     (START_X + 3*GRID_SIZE, START_Y + 7*GRID_SIZE), 
                     (START_X + 5*GRID_SIZE, START_Y + 9*GRID_SIZE), 2)
    # 右上到左下对角线
    pygame.draw.line(screen, LINE, 
                     (START_X + 5*GRID_SIZE, START_Y + 7*GRID_SIZE), 
                     (START_X + 3*GRID_SIZE, START_Y + 9*GRID_SIZE), 2)

def draw_pieces(selected=None):
    for pid, v in pieces.items():
        c, r, txt, col = v
        x = START_X + c*GRID_SIZE
        y = START_Y + r*GRID_SIZE
        
        # 选中高亮
        if pid == selected:
            # 【修改4】棋子高亮圈尺寸适配新GRID_SIZE（原GRID_SIZE//2-3，变量联动无需改）
            pygame.draw.circle(screen, HIGHLIGHT, (x,y), GRID_SIZE//2-3)
            
        # 【修改5】棋子绘制尺寸适配新GRID_SIZE（变量联动无需改）
        pygame.draw.circle(screen, col, (x,y), GRID_SIZE//2-6)
        pygame.draw.circle(screen, WHITE, (x,y), GRID_SIZE//2-6, 2)
        surf = font_big.render(txt, True, WHITE)
        rect = surf.get_rect(center=(x,y))
        screen.blit(surf, rect)

def pos_at_mouse(pos):
    mx, my = pos
    # 【修改6】鼠标坐标转棋盘坐标适配新START_X/START_Y/GRID_SIZE（变量联动无需改）
    c = round((mx - START_X)/GRID_SIZE)
    r = round((my - START_Y)/GRID_SIZE)
    return max(0, min(8, c)), max(0, min(9, r))

def piece_at(c, r):
    for pid, v in pieces.items():
        pc, pr, _, _ = v
        if pc == c and pr == r:
            return pid
    return None

# ==============================
# 主循环
# ==============================
def main():
    ai = Engine()
    selected = None
    info = "红方先行"
    run = True
    clock = pygame.time.Clock()
    player_turn = True # True=红方(人), False=黑方(AI)

    # 临时存储移动前的坐标，用于生成UCI指令
    move_start_pos = None 

    while run:
        draw_board()
        draw_pieces(selected)
        
        # 显示提示信息
        info_surf = font_small.render(info, True, (0,0,0))
        # 【修改7】提示文字位置适配新窗口高度（原WINDOW_H -25，变量联动无需改）
        screen.blit(info_surf, (10, WINDOW_H - 25))

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                run = False

            # --- 玩家走棋逻辑 ---
            if e.type == pygame.MOUSEBUTTONDOWN and player_turn:
                c, r = pos_at_mouse(e.pos)
                clicked_pid = piece_at(c, r)

                # 1. 如果还没选中棋子，必须点红棋
                if selected is None:
                    if clicked_pid and pieces[clicked_pid][3] == RED:
                        selected = clicked_pid
                        move_start_pos = (c, r) # 记录起点
                        info = f"选中 {pieces[selected][2]}"
                    else:
                        info = "请选红棋"
                
                # 2. 如果已经选中了，准备移动
                else:
                    # 如果点到了自己的棋子，更换选中
                    if clicked_pid and pieces[clicked_pid][3] == RED:
                        selected = clicked_pid
                        move_start_pos = (c, r)
                        info = f"切换选中 {pieces[selected][2]}"
                    else:
                        # 尝试移动 (此处没有写规则验证，只是简单移动)
                        # 生成UCI移动字符串
                        start_c, start_r = move_start_pos
                        uci_move = xy_to_uci(start_c, start_r) + xy_to_uci(c, r)
                        
                        # 执行移动
                        success = apply_move_logic(start_c, start_r, c, r)
                        if success:
                            move_history.append(uci_move) # 存入历史
                            selected = None
                            info = "AI思考中..."
                            player_turn = False # 轮到AI
                        else:
                            info = "移动失败"

        # --- AI走棋逻辑 ---
        if not player_turn:
            # 强制刷新一下界面，让玩家看到刚才走的红棋
            pygame.display.flip()
            
            # 传入整个走棋历史给AI
            best_mv = ai.bestmove(move_history)
            
            if best_mv:
                # 解析AI的UCI字符串
                f_uci = best_mv[:2]
                t_uci = best_mv[2:]
                f_pos = uci_to_pos(f_uci)
                t_pos = uci_to_pos(t_uci)
                
                if f_pos and t_pos:
                    apply_move_logic(f_pos[0], f_pos[1], t_pos[0], t_pos[1])
                    move_history.append(best_mv) # 记录AI的招法
                    info = f"AI走: {best_mv}"
                else:
                    info = f"AI返回无效坐标: {best_mv}"
            else:
                info = "AI无响应或出错"
            
            player_turn = True # 回到玩家回合

        pygame.display.flip()
        clock.tick(30)

    if ai.p:
        ai.p.kill()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()