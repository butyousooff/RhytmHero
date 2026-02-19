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
    pygame.init()
    pygame.mixer.pre_init(44100, -16, 2, 512)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Rhythm Hero")
    clock = pygame.time.Clock()

    global game_time, game_notes, score, hits, misses, note_speed

    game_notes = []
    for i in range(20):
        game_notes.append({
            'start_time': i * 0.5,
            'lane': i % LANES,
            'note': 60 + (i % 4) * 5,
            'hit': False
        })

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        game_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key in KEYS:
                    lane = KEYS[event.key]
                    active = spawn_active_notes(game_notes, game_time, note_speed)

                    if check_hit(lane, active):
                        score += 100
                        hits += 1

                        for n in active:
                            if n['lane'] == lane and n['data']['hit']:
                                play_note_sound(n['data']['note'])
                                break
                        print(f"Hit! Score: {score}")
                    else:
                        misses += 1
                        print(f"Miss! Misses: {misses}")

        screen.fill((0, 0, 0))
        draw_lanes(screen)

        active_notes = spawn_active_notes(game_notes, game_time, note_speed)
        draw_notes(screen, active_notes)

        font = pygame.font.Font(None, 32)
        ui_text = f"Score: {score} | Hits: {hits} | Miss: {misses}"
        screen.blit(font.render(ui_text, True, (255, 255, 255)), (15, 12))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    os.makedirs('songs', exist_ok=True)

    midi_files = [f for f in os.listdir('songs') if f.endswith('.mid')]

    if midi_files:
        filepath = os.path.join('songs', midi_files[0])
        tracks = analyze_midi_file(filepath)
        if tracks:
            notes = load_notes_from_tracks(tracks, [0], bpm=120)
            print(f"Загружено {len(notes)} нот")
    else:
        print("Положи .mid файлы в папку songs/")
