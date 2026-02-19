import pygame, sys, mido, os, numpy as np, threading, time

W, H, FPS = 1100, 700, 60
LANES, LANE_W = 4, 1100 // 4
HIT_Y, DEF_SPEED, DEF_BPM = H - 100, 300, 120

KEYS = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3}
KEY_NAMES = ['Q', 'W', 'E', 'R']
LANE_COL = [(255, 100, 100), (100, 255, 100), (100, 100, 255), (255, 255, 100)]
MENU, TRACK_SEL, PLAYING, PAUSED, GAMEOVER = range(5)

settings = {'speed': DEF_SPEED, 'bpm': DEF_BPM}
hit_cache = {}
preview_active = False
tracks_data = []
notes_queue = []
note_idx = 0
game_time = 0.0
score = 0
hits = 0
misses = 0
max_score = 0
active_notes = []

def midi_to_freq(n):
    return 440 * (2 ** ((n - 69) / 12))

def init_audio():
    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.mixer.init(44100, -16, 2, 512)
        return True
    except Exception:
        pygame.init()
        return False

def gen_sound(freq, dur=0.15, vol=0.4):
    if freq <= 0:
        freq = 440
    sr = 44100
    n = int(sr * dur)
    t = np.linspace(0, dur, n, False)
    wave = np.sin(2 * np.pi * freq * t)
    env = np.ones(n)
    env[:int(n * 0.1)] = np.linspace(0, 1, int(n * 0.1))
    env[-int(n * 0.3):] = np.linspace(1, 0, int(n * 0.3))
    audio = np.int16(wave * env * vol * 32767)
    return pygame.sndarray.make_sound(np.column_stack((audio, audio)))

def get_sound(note):
    if note not in hit_cache:
        try:
            hit_cache[note] = gen_sound(midi_to_freq(note))
        except Exception:
            return None
        if len(hit_cache) > 50:
            hit_cache.pop(next(iter(hit_cache)))
    return hit_cache.get(note)

def preview_notes(notes, bpm_val):
    global preview_active
    preview_active = True
    mult = bpm_val / 120.0
    start = time.time()
    for n in sorted(notes, key=lambda x: x['time']):
        if not preview_active:
            break
        wait = (n['time'] / mult) - (time.time() - start)
        if wait > 0:
            time.sleep(min(wait, 0.3))
        s = get_sound(n['note'])
        if s:
            s.play()
        if time.time() - start > 8:
            break
    preview_active = False

def analyze_midi(path):
    if not os.path.exists(path):
        return []
    try:
        mid = mido.MidiFile(path)
    except Exception:
        return []
    result = []
    for i, tr in enumerate(mid.tracks):
        notes = []
        abs_t = 0
        tempo = 500000
        name = "Track " + str(i + 1)
        for msg in tr:
            abs_t += msg.time
            if msg.type == 'set_tempo':
                tempo = msg.tempo
            if msg.type == 'track_name':
                name = msg.name
            if msg.type == 'note_on' and msg.velocity > 0:
                notes.append({
                    'note': msg.note,
                    'time': mido.tick2second(abs_t, mid.ticks_per_beat, tempo),
                    'velocity': msg.velocity
                })
        if notes:
            vals = [n['note'] for n in notes]
            result.append({
                'idx': i,
                'name': name,
                'notes': notes,
                'count': len(notes),
                'min': min(vals),
                'max': max(vals),
                'selected': True
            })
    return result

def load_notes(tracks, bpm_val):
    mult = 120.0 / bpm_val
    all_n = []
    for t in tracks:
        if not t['selected']:
            continue
        for n in t['notes']:
            all_n.append({
                't': n['time'] * mult,
                'lane': n['note'] % LANES,
                'note': n['note'],
                'hit': False
            })
    all_n.sort(key=lambda x: x['t'])
    last = [-1000] * LANES
    filtered = []
    for n in all_n:
        if n['t'] - last[n['lane']] > 0.05:
            filtered.append(n)
            last[n['lane']] = n['t']
    return filtered

def draw_btn(scr, txt, x, y, w, h, col, hcol, mpos, en=True):
    rect = pygame.Rect(x, y, w, h)
    hover = rect.collidepoint(mpos) if en else False
    cur = hcol if hover and en else (col if en else (80, 80, 100))
    pygame.draw.rect(scr, cur, rect, border_radius=8)
    pygame.draw.rect(scr, (255, 255, 255) if en else (150, 150, 150), rect, 2, border_radius=8)
    f = pygame.font.Font(None, 28)
    t = f.render(txt, True, (255, 255, 255) if en else (180, 180, 180))
    scr.blit(t, t.get_rect(center=rect.center))
    return rect

def draw_menu(scr, songs, sel, mpos):
    scr.fill((18, 18, 38))
    fl = pygame.font.Font(None, 72)
    fm = pygame.font.Font(None, 38)
    title = fl.render("RHYTHM HERO", True, (255, 255, 255))
    scr.blit(title, (W // 2 - title.get_width() // 2, 150))
    y = 250
    if not songs:
        warn = fm.render("Put .mid files in 'songs/' folder", True, (255, 150, 150))
        scr.blit(warn, (W // 2 - warn.get_width() // 2, y))
        y += 50
    select = fm.render("Select a song:", True, (200, 200, 220))
    scr.blit(select, (W // 2 - select.get_width() // 2, y))
    y += 50
    rects = []
    for i, s in enumerate(songs):
        c = (90, 90, 180) if i != sel else (130, 130, 240)
        hc = (130, 130, 240) if i != sel else (180, 180, 255)
        name = s.replace('.mid', '')[:30]
        rects.append((draw_btn(scr, name, W // 2 - 200, y + i * 55, 400, 45, c, hc, mpos), i))
    en = len(songs) > 0
    play = draw_btn(scr, "Next", W // 2 - 100, y + len(songs) * 55 + 40, 200, 50,
                    (40, 180, 40) if en else (80, 100, 80),
                    (60, 220, 60) if en else (100, 120, 100), mpos, en)
    return rects, play

def draw_track_sel(scr, tracks, mpos):
    scr.fill((18, 18, 38))
    fl = pygame.font.Font(None, 64)
    fm = pygame.font.Font(None, 36)
    fs = pygame.font.Font(None, 26)
    title = fl.render("TRACK SELECTION", True, (255, 255, 255))
    scr.blit(title, (W // 2 - title.get_width() // 2, 15))
    y0 = 85
    t_rects = []
    p_btns = []
    visible = tracks[:7]
    for i, tr in enumerate(visible):
        y = y0 + i * 60
        pygame.draw.rect(scr, (30, 30, 60) if tr['selected'] else (25, 25, 40),
                        pygame.Rect(40, y, W - 220, 50), border_radius=8)
        pygame.draw.rect(scr, (100, 100, 150) if tr['selected'] else (60, 60, 90),
                        pygame.Rect(40, y, W - 220, 50), 2, border_radius=8)
        cb = pygame.Rect(60, y + 10, 26, 26)
        pygame.draw.rect(scr, (50, 200, 50) if tr['selected'] else (100, 100, 100), cb, border_radius=4)
        if tr['selected']:
            pygame.draw.circle(scr, (255, 255, 255), cb.center, 6)
        scr.blit(fm.render(tr['name'], True, (255, 255, 255)), (100, y + 6))
        details = "Notes: " + str(tr['count']) + " | " + str(tr['min']) + "-" + str(tr['max'])
        scr.blit(fs.render(details, True, (180, 180, 200)), (100, y + 28))
        p_btns.append((draw_btn(scr, ">", W - 170, y + 7, 45, 35, (80, 80, 160), (120, 120, 220), mpos), i))
        t_rects.append((cb, i))
    sy = y0 + min(len(tracks), 7) * 60 + 15
    pygame.draw.rect(scr, (25, 25, 50), pygame.Rect(40, sy, W - 80, 90), border_radius=10)
    pygame.draw.rect(scr, (80, 80, 120), pygame.Rect(40, sy, W - 80, 90), 2, border_radius=10)
    scr.blit(fs.render("SETTINGS", True, (200, 200, 220)), (60, sy + 8))
    scr.blit(fs.render("Speed:", True, (180, 180, 200)), (60, sy + 35))
    s_m = draw_btn(scr, "-", 200, sy + 30, 35, 30, (80, 80, 140), (120, 120, 200), mpos)
    scr.blit(fm.render(str(settings['speed']), True, (255, 255, 255)), (245, sy + 32))
    s_p = draw_btn(scr, "+", 290, sy + 30, 35, 30, (80, 80, 140), (120, 120, 200), mpos)
    scr.blit(fs.render("BPM:", True, (180, 180, 200)), (350, sy + 35))
    b_m = draw_btn(scr, "-", 480, sy + 30, 35, 30, (80, 80, 140), (120, 120, 200), mpos)
    scr.blit(fm.render(str(settings['bpm']), True, (255, 255, 255)), (525, sy + 32))
    b_p = draw_btn(scr, "+", 575, sy + 30, 35, 30, (80, 80, 140), (120, 120, 200), mpos)
    by = sy + 100
    sa = draw_btn(scr, "Select All", 100, by, 120, 38, (60, 100, 160), (80, 130, 200), mpos)
    sd = draw_btn(scr, "Deselect All", 240, by, 120, 38, (100, 80, 80), (140, 100, 100), mpos)
    sel_c = sum(1 for t in tracks if t['selected'])
    play_b = draw_btn(scr, "PLAY", W // 2 - 90, by, 180, 48,
                      (40, 160, 40) if sel_c else (80, 100, 80),
                      (60, 200, 60) if sel_c else (100, 120, 100), mpos, sel_c > 0)
    back = draw_btn(scr, "Back", W // 2 - 70, by + 60, 140, 38, (100, 100, 100), (140, 140, 140), mpos)
    info = "Tracks: " + str(len(tracks)) + " | Selected: " + str(sel_c)
    scr.blit(fs.render(info, True, (150, 150, 180)), (W // 2 - 80, by + 110))
    return {
        't_rects': t_rects, 'p_btns': p_btns, 's_m': s_m, 's_p': s_p,
        'b_m': b_m, 'b_p': b_p, 'sa': sa, 'sd': sd, 'play': play_b, 'back': back
    }

def draw_game(scr):
    scr.fill((0, 0, 0))
    for i in range(LANES):
        x = i * LANE_W
        pygame.draw.line(scr, (60, 60, 80), (x, 0), (x, H), 2)
        pygame.draw.rect(scr, (25, 25, 50), (x, HIT_Y, LANE_W, 100))
        pygame.draw.rect(scr, (80, 80, 120), (x, HIT_Y, LANE_W, 100), 2)
        f = pygame.font.Font(None, 52)
        txt = f.render(KEY_NAMES[i], True, (220, 220, 255))
        scr.blit(txt, txt.get_rect(center=(x + LANE_W // 2, HIT_Y + 50)))
    for lane, y, data in active_notes:
        col = LANE_COL[lane] if not data['hit'] else (150, 150, 150)
        pygame.draw.rect(scr, col, (lane * LANE_W + 12, y, LANE_W - 24, 18), border_radius=4)
    f = pygame.font.Font(None, 32)
    ui = "Score: " + str(score) + "  |  Hits: " + str(hits) + "  |  Miss: " + str(misses)
    scr.blit(f.render(ui, True, (255, 255, 255)), (15, 12))
    pygame.draw.rect(scr, (0, 0, 0, 180), (W // 2 - 60, 10, 120, 30))
    scr.blit(f.render("P - Pause", True, (200, 200, 255)), (W // 2 - 50, 15))

def draw_pause(scr):
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 30, 200))
    scr.blit(overlay, (0, 0))
    fl = pygame.font.Font(None, 64)
    fm = pygame.font.Font(None, 36)
    title = fl.render("PAUSED", True, (255, 255, 255))
    scr.blit(title, (W // 2 - title.get_width() // 2, 150))
    y = 250
    scr.blit(fm.render("Speed: " + str(settings['speed']), True, (200, 200, 220)), (W // 2 - 80, y))
    sm = draw_btn(scr, "-", W // 2 - 120, y + 30, 40, 40, (80, 80, 140), (120, 120, 200), pygame.mouse.get_pos())
    scr.blit(fm.render(str(settings['speed']), True, (255, 255, 255)), (W // 2 - 30, y + 35))
    sp = draw_btn(scr, "+", W // 2 + 80, y + 30, 40, 40, (80, 80, 140), (120, 120, 200), pygame.mouse.get_pos())
    scr.blit(fm.render("BPM: " + str(settings['bpm']), True, (200, 200, 220)), (W // 2 - 60, y + 90))
    bm = draw_btn(scr, "-", W // 2 - 120, y + 120, 40, 40, (80, 80, 140), (120, 120, 200), pygame.mouse.get_pos())
    scr.blit(fm.render(str(settings['bpm']), True, (255, 255, 255)), (W // 2 - 30, y + 125))
    bp = draw_btn(scr, "+", W // 2 + 80, y + 120, 40, 40, (80, 80, 140), (120, 120, 200), pygame.mouse.get_pos())
    resume = draw_btn(scr, "Resume", W // 2 - 100, y + 190, 200, 50, (40, 160, 40), (60, 200, 60), pygame.mouse.get_pos())
    track_sel_b = draw_btn(scr, "Tracks", W // 2 - 100, y + 250, 200, 45, (100, 100, 180), (130, 130, 220), pygame.mouse.get_pos())
    menu_b = draw_btn(scr, "Menu", W // 2 - 100, y + 305, 200, 45, (100, 100, 100), (140, 140, 140), pygame.mouse.get_pos())
    return {
        'sm': sm, 'sp': sp, 'bm': bm, 'bp': bp,
        'resume': resume, 'tracks': track_sel_b, 'menu': menu_b
    }

def draw_gameover(scr):
    scr.fill((18, 18, 38))
    fl = pygame.font.Font(None, 72)
    fm = pygame.font.Font(None, 42)
    title = fl.render("GAME OVER", True, (255, 255, 255))
    scr.blit(title, (W // 2 - title.get_width() // 2, 150))
    scr.blit(fm.render("Score: " + str(score), True, (255, 220, 100)), (W // 2 - 60, 250))
    if max_score > 0:
        acc = min(100, int(score / max_score * 100))
        scr.blit(fm.render("Accuracy: " + str(acc) + "%", True, (150, 200, 255)), (W // 2 - 90, 310))
    stats = "Hits: " + str(hits) + "  |  Misses: " + str(misses)
    scr.blit(fm.render(stats, True, (180, 180, 200)), (W // 2 - 150, 370))
    scr.blit(fm.render("ENTER - menu  |  ESC - exit", True, (180, 180, 200)), (W // 2 - 140, 450))
    menu_btn = draw_btn(scr, "Menu", W // 2 - 80, 500, 160, 45, (100, 100, 180), (130, 130, 220), pygame.mouse.get_pos())
    return menu_btn

def get_midi_files(folder="songs"):
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except Exception:
            pass
        return []
    try:
        files = [f for f in os.listdir(folder) if f.endswith('.mid')]
        return files
    except Exception:
        return []

def update_active_notes():
    global note_idx, active_notes, game_time
    speed = settings['speed']
    new_active = []
    for lane, old_y, data in active_notes:
        time_diff = data['t'] - game_time
        y = HIT_Y - (time_diff * speed)
        if -60 < y < H + 60 and not data['hit']:
            new_active.append((lane, y, data))
    active_notes = new_active
    while note_idx < len(notes_queue):
        note = notes_queue[note_idx]
        if note.get('hit', False):
            note_idx += 1
            continue
        time_diff = note['t'] - game_time
        y = HIT_Y - (time_diff * speed)
        if y > H + 60:
            note_idx += 1
        elif y >= -60:
            active_notes.append((note['lane'], y, note))
            note_idx += 1
        else:
            break

def check_hit(lane):
    for i, (ln, y, data) in enumerate(active_notes):
        if ln == lane and not data['hit'] and abs(y - HIT_Y) < 60:
            data['hit'] = True
            return True
    return False

def safe_state_change(new_state):
    global state, game_time, note_idx, active_notes
    if new_state == MENU:
        game_time = 0.0
        note_idx = 0
        active_notes = []
    return new_state

def main():
    global tracks_data, notes_queue, note_idx, game_time
    global score, hits, misses, max_score, active_notes, preview_active, state
    if not init_audio():
        print("Warning: Running without audio")
    try:
        screen = pygame.display.set_mode((W, H), pygame.DOUBLEBUF)
        pygame.display.set_caption("Rhythm Hero")
    except Exception as e:
        print("Error creating window:", e)
        pygame.quit()
        sys.exit(1)
    clock = pygame.time.Clock()

    songs = get_midi_files("songs")
    sel_song = 0 if songs else -1
    state = MENU
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        mpos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_p:
                    if state == PLAYING:
                        state = PAUSED
                    elif state == PAUSED:
                        state = PLAYING
                    elif state == TRACK_SEL:
                        state = MENU
                if state == GAMEOVER and event.key == pygame.K_RETURN:
                    state = MENU
                if state == PLAYING and event.key in KEYS:
                    if check_hit(KEYS[event.key]):
                        score += 100
                        hits += 1
                        for ln, y, data in active_notes:
                            if ln == KEYS[event.key] and data['hit']:
                                s = get_sound(data['note'])
                                if s:
                                    s.play()
                                break
                    else:
                        score = max(0, score - 5)
                        misses += 1
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                try:
                    if state == MENU:
                        s_rects, play_r = draw_menu(screen, songs, sel_song, mpos)
                        for r, i in s_rects:
                            if r.collidepoint(mpos):
                                sel_song = i
                        if play_r.collidepoint(mpos) and sel_song >= 0:
                            path = os.path.join("songs", songs[sel_song])
                            tracks_data = analyze_midi(path)
                            if tracks_data:
                                state = TRACK_SEL
                            else:
                                print("No notes in file")
                    elif state == TRACK_SEL:
                        ui = draw_track_sel(screen, tracks_data, mpos)
                        for cb, i in ui['t_rects']:
                            if cb.collidepoint(mpos):
                                tracks_data[i]['selected'] = not tracks_data[i]['selected']
                        for pb, i in ui['p_btns']:
                            if pb.collidepoint(mpos) and not preview_active:
                                thread = threading.Thread(target=preview_notes,
                                                        args=(tracks_data[i]['notes'], settings['bpm']),
                                                        daemon=True)
                                thread.start()
                        if ui['s_m'].collidepoint(mpos):
                            settings['speed'] = max(100, settings['speed'] - 50)
                        if ui['s_p'].collidepoint(mpos):
                            settings['speed'] = min(700, settings['speed'] + 50)
                        if ui['b_m'].collidepoint(mpos):
                            settings['bpm'] = max(60, settings['bpm'] - 10)
                        if ui['b_p'].collidepoint(mpos):
                            settings['bpm'] = min(300, settings['bpm'] + 10)
                        if ui['sa'].collidepoint(mpos):
                            for t in tracks_data:
                                t['selected'] = True
                        if ui['sd'].collidepoint(mpos):
                            for t in tracks_data:
                                t['selected'] = False
                        if ui['play'].collidepoint(mpos) and any(t['selected'] for t in tracks_data):
                            notes_queue = load_notes(tracks_data, settings['bpm'])
                            if notes_queue:
                                note_idx = 0
                                game_time = 0.0
                                score = 0
                                hits = 0
                                misses = 0
                                max_score = len(notes_queue) * 100
                                active_notes = []
                                state = PLAYING
                        if ui['back'].collidepoint(mpos):
                            state = MENU
                    elif state == PAUSED:
                        ui = draw_pause(screen)
                        if ui['sm'].collidepoint(mpos):
                            settings['speed'] = max(150, settings['speed'] - 50)
                        if ui['sp'].collidepoint(mpos):
                            settings['speed'] = min(700, settings['speed'] + 50)
                        if ui['bm'].collidepoint(mpos):
                            settings['bpm'] = max(60, settings['bpm'] - 10)
                        if ui['bp'].collidepoint(mpos):
                            settings['bpm'] = min(200, settings['bpm'] + 10)
                        if ui['resume'].collidepoint(mpos):
                            state = PLAYING
                        if ui['tracks'].collidepoint(mpos):
                            state = TRACK_SEL
                        if ui['menu'].collidepoint(mpos):
                            state = MENU
                    elif state == GAMEOVER:
                        menu_btn = draw_gameover(screen)
                        if menu_btn.collidepoint(mpos):
                            state = MENU
                except Exception as e:
                    print("Mouse event error:", e)
        try:
            if state == MENU:
                draw_menu(screen, songs, sel_song, mpos)
            elif state == TRACK_SEL:
                draw_track_sel(screen, tracks_data, mpos)
            elif state == PLAYING:
                game_time += dt
                update_active_notes()
                draw_game(screen)
                if notes_queue and note_idx >= len(notes_queue) and not active_notes:
                    state = GAMEOVER
            elif state == PAUSED:
                draw_pause(screen)
            elif state == GAMEOVER:
                draw_gameover(screen)
        except Exception as e:
            print("Draw error:", e)
        pygame.display.flip()

    preview_active = False
    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        pygame.quit()
        sys.exit(0)
    except Exception as e:
        print("Critical error:", e)
        pygame.quit()
        sys.exit(1)
