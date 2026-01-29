import os
import pyautogui
import time
import re
import keyboard
import cv2
import numpy as np
import threading
import random
import pyperclip

#목표레벨
TARGET_LEVEL = 20

##########################
# 좌표 어긋나면 난리 나요!! #
##########################

# 좌표 설정
CHAT_X, CHAT_Y = 200, 960       # 채팅 입력 위치

# 대화 영역 박스
CHATBOX_X1, CHATBOX_Y1 = 10, 100  # 좌상단 좌표
CHATBOX_X2, CHATBOX_Y2 = 340, 910 # 우하단 좌표

# 상태 변수
running = False
lock = threading.Lock()
stats = {}  # 통계 결과

# '/강화' 입력 
def enhance_once():
    # 채팅창 포커스
    pyautogui.click(CHAT_X, CHAT_Y)
    time.sleep(0.05)

    # '/강화' 직접 입력
    pyautogui.write('/강화', interval=0.02)

    # 엔터 두 번
    pyautogui.press('enter')
    time.sleep(0.05)
    pyautogui.press('enter')
    time.sleep(0.05)

# 대화 영역 캡쳐 
def capture_roi():
    img = pyautogui.screenshot(region=(
        CHATBOX_X1,
        CHATBOX_Y1,
        CHATBOX_X2 - CHATBOX_X1,
        CHATBOX_Y2 - CHATBOX_Y1
    ))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)

# 강화 결과 대기
def wait_for_roi_change(baseline, timeout=10.0):
    start = time.time()

    while time.time() - start < timeout:
        current = capture_roi()

        diff = cv2.absdiff(baseline, current)
        changed_pixels = np.count_nonzero(diff > 25)

        # 임계값은 환경 따라 조절 (보통 수천 단위)
        if changed_pixels > 3000:
            return True

        time.sleep(0.1)

    return False

# 결과 문자 인식
def copy_roi_text():
    # 기존 클립보드 비우기
    pyperclip.copy('')

    # ROI 드래그 선택
    pyautogui.moveTo(CHATBOX_X1, CHATBOX_Y1)
    time.sleep(0.02)
    pyautogui.dragTo(
        CHATBOX_X2, CHATBOX_Y2,
        duration=0.2,
        button='left'
    )
    time.sleep(0.02)

    # 복사
    pyautogui.hotkey('ctrl', 'c')

    # 클립보드 반영 대기
    time.sleep(0.05)

    pyautogui.click(CHATBOX_X1, CHATBOX_Y1)

    text = pyperclip.paste()
    key = '@사용자 〖'
    idx = text.rfind(key)
    if idx != -1:
        text = text[idx + len(key) -1:]
    else :
        print('사용자 이름 확인 불가')
    print(text)

    return text

# 결과 판별 + 레벨 갱신
def parse_enhance_result(text: str, prev_level: int):
    """
    반환:
        result_dict['result'] (str): SUCCESS / KEEP / DESTROY / UNKNOWN
        result_dict['level'] (int): 현재 강화 단계
        result_dict['gold'] (int | None): 남은 골드
        result_dict['use_gold'] (int | None): 사용 골드
    """
    result_dict = dict()

    # ---------- 결과 판별 ----------
    s = text.replace('\n', '').replace(' ', '')

    if '강화성공' in s:
        result_dict['result'] = 'SUCCESS'
    elif '강화유지' in s:
        result_dict['result'] = 'KEEP'
    elif '강화파괴' in s:
        result_dict['result'] = 'DESTROY'
    else:
        result_dict['result'] = 'UNKNOWN'

    # ---------- 레벨 추출 ----------
    # +6 → +7, ~6 → ~7, [+7] 전부 커버
    nums = re.findall(r'\[\s*\+\s*(\d+)\s*\]', text)
    if nums:
        result_dict['level'] = int(nums[-1])   # 항상 "마지막 숫자"가 현재 레벨
    else:
        result_dict['level'] = prev_level      # 못 찾으면 이전 값 유지

    # ---------- 남은 골드 ----------
    m = re.search(r'남은\s*골드\s*:\s*([\d,]+)\s*G', text)
    if m:
        result_dict['gold']  = int(m.group(1).replace(',', ''))
    else:
        result_dict['gold']  = None

    # ---------- 사용 골드 ----------
    m = re.search(r'사용\s*골드\s*: -\s*([\d,]+)\s*G', text)
    if m:
        result_dict['use_gold']  = int(m.group(1).replace(',', ''))
    else:
        result_dict['use_gold']  = None

    return result_dict

# 통계
def update_stats(result, level, prev_level, use_gold):
    if  result == 'SUCCESS':
        stat_level = level - 1
    elif result == 'DESTROY':
        stat_level = prev_level
    else:
        stat_level = level
        
    if stat_level not in stats:
        stats[stat_level] = {
            'SUCCESS': 0,
            'KEEP': 0,
            'DESTROY': 0,
            'UNKNOWN': 0,
            'TOTAL_GOLD': 0
        }

    stats[stat_level][result] += 1

    if use_gold is not None:
        stats[stat_level]['TOTAL_GOLD'] += use_gold

### 메인 루프 ###
def main_loop():
    global running
    result_dict = parse_enhance_result(copy_roi_text(), 0)
    prev_level = result_dict['level']
    print("\n🚀 강화 매크로 시작")

    while True:
        with lock:
            if not running:
                break
        print("=============================================================")
        print(f"< lv{prev_level} → lv{prev_level + 1} 강화 시도 >")

        enhance_once()                              # 강화 시도
        baseline = capture_roi()                    # 대화 영역 캡쳐
        changed = wait_for_roi_change(baseline)     # 대화 영역 변화 감지 대기

        if not changed:
            print("⚠ 결과 화면 변화 감지 실패")
            continue

        # 결과 출력 대기 (랜덤)
        time.sleep(random.uniform(0.03, 0.05))

        with lock:
            if not running:
                break

        text = copy_roi_text()                      # 결과 문자 인식
        result_dict = parse_enhance_result(text, prev_level)

        result = result_dict['result'] 
        level = result_dict['level']
        use_gold = result_dict['use_gold'] 
        gold = result_dict['gold'] 

        update_stats(result, level, prev_level, use_gold)
        
        print("+-------------------------------------------------------------+")
        print(f"| 결과 : {result}")
        print(f"| 현재 강화 단계 : +{level}")
        print(f"| 사용 골드 : {use_gold}")
        print(f"| 남은 골드 : {gold}")
        print("+-------------------------------------------------------------+")

        print("\n[ 통계 ]")
        print("레벨    성공   유지   파괴   미상   사용골드")
        for lv in sorted(stats.keys()):
            s = stats[lv]
            print(
                f"lv{lv:<2} {s['SUCCESS']:6} {s['KEEP']:6} {s['DESTROY']:6} {s['UNKNOWN']:6}    {s['TOTAL_GOLD']:>8}"
            )

        if level >= TARGET_LEVEL:
            print(f"\n🎉 목표 강화 +{TARGET_LEVEL} 도달 → 자동 중지")
            with lock:
                running = False
            break
        
        prev_level = level
        time.sleep(random.uniform(0.02, 0.05))

# 단축키
def start():
    global running
    with lock:
        if running:
            return
        running = True
    print("\n▶ 강화 시작")
    threading.Thread(target=main_loop, daemon=True).start()

def stop():
    global running
    with lock:
        running = False
    print("\n⛔ 수동 중지")

def close():
    print("\n프로그램 종료")
    os._exit(0)
    
###############################################################################    
#entry point

keyboard.add_hotkey('F8', start)
keyboard.add_hotkey('F9', stop)
keyboard.add_hotkey('F10', close)

result_dict = parse_enhance_result(copy_roi_text(), 0)
if result_dict['result'] == "UNKNOWN":
    print("화면 내에 현재 정보가 보이지 않습니다.")
    exit(0)
print("-------------------------------------------------------")
print(f"현재 강화 단계 : +{result_dict['level']}")
print(f"남은 골드 : {result_dict['gold']}")
print("✅ 준비 완료")
print("▶ F8 시작 / ⛔ F9 중지 / 종료 F10")
print("-------------------------------------------------------")

keyboard.wait()
