import pygame
import sys
import numpy as np
import mido
import os

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
LANES = 4
LANE_WIDTH = SCREEN_WIDTH // LANES
HIT_LINE_Y = SCREEN_HEIGHT - 100

KEYS = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3}
KEY_NAMES = ['Q', 'W', 'E', 'R']

hit_sounds = {}

game_notes = []
game_time = 0.0
note_speed = 300
score = 0
hits = 0
misses = 0

STATE_MENU = 0
STATE_PLAYING = 1
STATE_GAMEOVER = 2

current_state = STATE_MENU


def draw_menu(screen, songs, selected_idx, mouse_pos):
    screen.fill((18, 18, 38))

    font_large = pygame.font.Font(None, 72)
    font_medium = pygame.font.Font(None, 38)

    title = font_large.render("RHYTHM HERO", True, (255, 255, 255))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 150))

    y = 250
    if not songs:
        warn = font_medium.render("Put .mid files in 'songs/' folder", True, (255, 150, 150))
        screen.blit(warn, (SCREEN_WIDTH // 2 - warn.get_width() // 2, y))
        y += 50

    select_text = font_medium.render("Select a song:", True, (200, 200, 220))
    screen.blit(select_text, (SCREEN_WIDTH // 2 - select_text.get_width() // 2, y))
    y += 50

    song_rects = []
    for i, song in enumerate(songs):
        name = song.replace('.mid', '')[:30]
        color = (90, 90, 180) if i != selected_idx else (130, 130, 240)
        hover_color = (130, 130, 240) if i != selected_idx else (180, 180, 255)

        rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, y + i * 55, 400, 45)
        pygame.draw.rect(screen, color, rect, border_radius=8)
        pygame.draw.rect(screen, hover_color, rect, 2, border_radius=8)

        text = font_medium.render(name, True, (255, 255, 255))
        screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

        song_rects.append((rect, i))

    enabled = len(songs) > 0
    play_color = (40, 180, 40) if enabled else (80, 100, 80)
    play_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, y + len(songs) * 55 + 40, 200, 50)
    pygame.draw.rect(screen, play_color, play_rect, border_radius=8)
    play_text = font_medium.render("PLAY", True, (255, 255, 255))
    screen.blit(play_text,
                (play_rect.centerx - play_text.get_width() // 2, play_rect.centery - play_text.get_height() // 2))

    return song_rects, play_rect


def spawn_active_notes(notes, current_time, speed):
    active = []
    for note in notes:
        time_diff = note['start_time'] - current_time
        y = HIT_LINE_Y - (time_diff * speed)

        if -60 < y < SCREEN_HEIGHT + 60:
            active.append({
                'lane': note['lane'],
                'y': y,
                'data': note
            })

    return active


def draw_notes(screen, active_notes):
    for note in active_notes:
        lane = note['lane']
        y = note['y']
        color = (255, 100, 100) if not note['data']['hit'] else (100, 255, 100)

        x = lane * LANE_WIDTH + 12
        pygame.draw.rect(screen, color, (x, y, LANE_WIDTH - 24, 18), border_radius=4)


def check_hit(lane, active_notes):
    for note in active_notes:
        if note['lane'] == lane and not note['data']['hit']:
            if abs(note['y'] - HIT_LINE_Y) < 60:
                note['data']['hit'] = True
                return True
    return False


def analyze_midi_file(filepath):
    if not os.path.exists(filepath):
        print(f"Файл не найден: {filepath}")
        return []

    try:
        mid = mido.MidiFile(filepath)
        print(f"Загружен MIDI: {len(mid.tracks)} дорожек")
    except Exception as e:
        print(f"Ошибка чтения MIDI: {e}")
        return []

    tracks_info = []

    for i, track in enumerate(mid.tracks):
        notes = []
        abs_time = 0
        tempo = 500000

        for msg in track:
            abs_time += msg.time

            if msg.type == 'set_tempo':
                tempo = msg.tempo

            if msg.type == 'note_on' and msg.velocity > 0:
                seconds = mido.tick2second(abs_time, mid.ticks_per_beat, tempo)
                notes.append({
                    'note': msg.note,
                    'time': seconds,
                    'velocity': msg.velocity
                })

        if notes:
            note_nums = [n['note'] for n in notes]
            tracks_info.append({
                'index': i,
                'name': f"Track {i + 1}",
                'notes': notes,
                'count': len(notes),
                'min_note': min(note_nums),
                'max_note': max(note_nums)
            })
            print(f"  Дорожка {i}: {len(notes)} нот ({min(note_nums)}-{max(note_nums)})")

    return tracks_info


def load_notes_from_tracks(tracks_info, selected_indices, bpm=120):
    all_notes = []

    tempo_mult = 120.0 / bpm

    for track in tracks_info:
        if track['index'] not in selected_indices:
            continue

        for note_data in track['notes']:
            all_notes.append({
                'start_time': note_data['time'] * tempo_mult,
                'lane': note_data['note'] % LANES,
                'note': note_data['note'],
                'hit': False
            })

    all_notes.sort(key=lambda x: x['start_time'])

    filtered = []
    last_time = [-1000] * LANES

    for note in all_notes:
        lane = note['lane']
        if note['start_time'] - last_time[lane] > 0.05:
            filtered.append(note)
            last_time[lane] = note['start_time']

    return filtered


def midi_to_freq(note_number):
    return 440 * (2 ** ((note_number - 69) / 12))


def generate_sound(frequency=440, duration=0.15, volume=0.4):
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, False)

    wave = np.sin(2 * np.pi * frequency * t)

    attack = int(n_samples * 0.1)
    decay = int(n_samples * 0.3)
    envelope = np.ones(n_samples)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-decay:] = np.linspace(1, 0, decay)

    wave = wave * envelope * volume
    audio = np.int16(wave * 32767)

    stereo = np.column_stack((audio, audio))
    return pygame.sndarray.make_sound(stereo)


def play_note_sound(note_number):
    if note_number not in hit_sounds:
        freq = midi_to_freq(note_number)
        hit_sounds[note_number] = generate_sound(freq)
        if len(hit_sounds) > 50:
            hit_sounds.pop(next(iter(hit_sounds)))

    if note_number in hit_sounds:
        hit_sounds[note_number].play()


def draw_lanes(screen):
    for i in range(LANES):
        x = i * LANE_WIDTH
        pygame.draw.line(screen, (60, 60, 80), (x, 0), (x, SCREEN_HEIGHT), 2)
        pygame.draw.rect(screen, (25, 25, 50), (x, HIT_LINE_Y, LANE_WIDTH, 100))
        pygame.draw.rect(screen, (80, 80, 120), (x, HIT_LINE_Y, LANE_WIDTH, 100), 2)
        font = pygame.font.Font(None, 52)
        text = font.render(KEY_NAMES[i], True, (220, 220, 255))
        text_rect = text.get_rect(center=(x + LANE_WIDTH // 2, HIT_LINE_Y + 50))
        screen.blit(text, text_rect)


def main():
    global current_state, game_time, score, hits, misses

    pygame.init()
    pygame.mixer.pre_init(44100, -16, 2, 512)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Rhythm Hero")
    clock = pygame.time.Clock()

    songs = [f for f in os.listdir('songs') if f.endswith('.mid')] if os.path.exists('songs') else []
    selected_song = 0 if songs else -1

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if current_state == STATE_MENU:
                    song_rects, play_rect = draw_menu(screen, songs, selected_song, mouse_pos)

                    for rect, idx in song_rects:
                        if rect.collidepoint(mouse_pos):
                            selected_song = idx
                            print(f"Selected: {songs[idx]}")

                    if play_rect.collidepoint(mouse_pos) and selected_song >= 0:
                        filepath = os.path.join('songs', songs[selected_song])
                        tracks = analyze_midi_file(filepath)
                        if tracks:
                            game_notes = load_notes_from_tracks(tracks, [0], bpm=120)
                            game_time = 0.0
                            score = hits = misses = 0
                            current_state = STATE_PLAYING
                            print(f"Game started with {len(game_notes)} notes")

        if current_state == STATE_MENU:
            draw_menu(screen, songs, selected_song, mouse_pos)
        elif current_state == STATE_PLAYING:
            game_time += dt
            screen.fill((0, 0, 0))
            draw_lanes(screen)

            active = spawn_active_notes(game_notes, game_time, note_speed)
            draw_notes(screen, active)

            if game_notes and game_time > game_notes[-1]['start_time'] + 2:
                current_state = STATE_GAMEOVER

            font = pygame.font.Font(None, 32)
            ui = f"Score: {score} | Hits: {hits} | Miss: {misses}"
            screen.blit(font.render(ui, True, (255, 255, 255)), (15, 12))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
