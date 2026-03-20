import random
import os
import sys

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.properties import NumericProperty
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle

# Only import Android stuff on Android
if sys.platform == 'android':
    from kivy.permissions import Permission, request_permissions
    from kivy.storage.jsonstore import JsonStore

Window.size = (400, 600)


# ============ STORAGE ACCESS ============
class StorageAccess:
    """Handle phone storage, media and photo access (Android only)"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.permissions_granted = False
    
    def request_permissions(self):
        """Request storage permissions from user"""
        if sys.platform != 'android':
            print("⚠ Storage access only works on Android")
            return
        
        read_media_images = getattr(Permission, 'READ_MEDIA_IMAGES', 'android.permission.READ_MEDIA_IMAGES')
        read_media_video = getattr(Permission, 'READ_MEDIA_VIDEO', 'android.permission.READ_MEDIA_VIDEO')
        read_media_audio = getattr(Permission, 'READ_MEDIA_AUDIO', 'android.permission.READ_MEDIA_AUDIO')

        permissions = [
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            read_media_images,
            read_media_video,
            read_media_audio,
            Permission.ACCESS_MEDIA_LOCATION,
        ]
        request_permissions(permissions, self.on_permissions_result)
    
    def on_permissions_result(self, permissions, grant_status):
        """Callback when user responds to permission request"""
        if all(grant_status):
            self.permissions_granted = True
            print("✓ Storage permissions granted!")
            self.access_all_media()
        else:
            print("✗ Permissions denied")
    
    def access_all_media(self):
        """Get all photos and media from phone"""
        try:
            media_paths = [
                "/sdcard/DCIM/Camera",
                "/sdcard/Pictures",
                "/sdcard/Download",
                "/sdcard/Movies",
                "/storage/emulated/0/DCIM",
                "/storage/emulated/0/Pictures",
            ]
            
            all_media = []
            for path in media_paths:
                if os.path.exists(path):
                    for filename in os.listdir(path):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mkv')):
                            full_path = os.path.join(path, filename)
                            all_media.append(full_path)
            
            print(f"✓ Found {len(all_media)} media files")
            return all_media
        
        except Exception as e:
            print(f"Error accessing media: {e}")
            return []
    
    def get_photos_only(self):
        """Get only photos"""
        try:
            photos = []
            photo_paths = [
                "/sdcard/Pictures",
                "/sdcard/DCIM/Camera",
                "/storage/emulated/0/Pictures"
            ]
            
            for path in photo_paths:
                if os.path.exists(path):
                    for filename in os.listdir(path):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                            photos.append(os.path.join(path, filename))
            
            return photos
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def save_game_data(self, data):
        """Save game data to storage"""
        if sys.platform != 'android':
            print("Game data not saved (not on Android)")
            return
        
        try:
            os.makedirs('/sdcard/FlappyBird', exist_ok=True)
            store = JsonStore('/sdcard/FlappyBird/game_data.json')
            store.put('save', **data)
            print("✓ Game data saved")
        except Exception as e:
            print(f"Error saving: {e}")


# ============ BIRD ============
class Bird(Widget):
    velocity = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sprite = Image(source="Bird.png")
        self.add_widget(self.sprite)
        self.bind(pos=self.update_graphics, size=self.update_graphics)
        self.update_graphics()

    def update_graphics(self, *args):
        self.sprite.pos = self.pos
        self.sprite.size = self.size

    def jump(self):
        self.velocity = 6


# ============ PIPE ============
class Pipe(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(0, 0.7, 0, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_graphics, size=self.update_graphics)

    def update_graphics(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


# ============ GAME ============
class Game(Widget):
    gravity = -0.2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg = Rectangle(source="bg.png", size=self.size, pos=self.pos)

        self.bind(size=self.update_bg, pos=self.update_bg)

        self.bird = Bird(size=(80, 80), pos=(100, 300))
        self.add_widget(self.bird)

        self.jump_sound = None
        self.jump_sound_fallback = None
        self._load_jump_sound()

        self.music_volume = 0.5
        self.bg_music = None
        self.bg_music_backend = None
        self._load_background_music()

        self.pipes = []
        self.pipe_speed = 1.5
        self.max_pipe_speed = 4.0
        self.speed_acceleration = 0.12

        self.score = 0
        self.score_label = Label(text="Score: 0", pos=(140, 550), font_size=20)
        self.add_widget(self.score_label)

        self.started = False

        self.start_btn = Button(text="START", size=(200, 60), pos=(100, 250), font_size=24)
        self.start_btn.bind(on_press=self.start_game)
        self.add_widget(self.start_btn)

        self.restart_btn = Button(text="RESTART", size=(200, 60), pos=(100, 250), font_size=24)
        self.restart_btn.bind(on_press=self.restart_game)

        Clock.schedule_interval(self.update, 1 / 60)
        Clock.schedule_interval(self.spawn_pipe, 2.5)

    def update_bg(self, *args):
        self.bg.size = self.size
        self.bg.pos = self.pos

    def start_game(self, instance):
        self.started = True
        self.pipe_speed = 1.5
        if self.start_btn.parent:
            self.remove_widget(self.start_btn)
        if self.restart_btn.parent:
            self.remove_widget(self.restart_btn)

    def restart_game(self, instance):
        self.bird.pos = (100, 300)
        self.bird.velocity = 0
        self.score = 0
        self.score_label.text = "Score: 0"

        for pipe in self.pipes:
            self.remove_widget(pipe["bottom"])
            self.remove_widget(pipe["top"])

        self.pipes.clear()
        self.started = True
        self.pipe_speed = 1.5

        if self.restart_btn.parent:
            self.remove_widget(self.restart_btn)

    def on_touch_down(self, touch):
        if self.started:
            self.bird.jump()
            self.play_jump_sound()
        return super().on_touch_down(touch)

    def _load_jump_sound(self):
        sound_path = os.path.join(
            os.path.dirname(__file__),
            "freesound_community-flappy_whoosh-43099.mp3"
        )

        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.jump_sound_fallback = pygame.mixer.Sound(sound_path)
            self.jump_sound_fallback.set_volume(1.0)
        except Exception:
            self.jump_sound_fallback = None

        self.jump_sound = SoundLoader.load(sound_path)
        if self.jump_sound:
            self.jump_sound.volume = 1.0

    def _load_background_music(self):
        preferred_path = os.path.join(os.path.dirname(__file__), "Courtside Original.mp3")
        fallback_path = os.path.join(os.path.dirname(__file__), "bgMusic.mp3")
        music_path = preferred_path if os.path.exists(preferred_path) else fallback_path

        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1)
            self.bg_music_backend = "pygame"
            return
        except Exception:
            self.bg_music_backend = None

        self.bg_music = SoundLoader.load(music_path)
        if self.bg_music:
            self.bg_music.volume = self.music_volume
            self.bg_music.loop = True
            self.bg_music.play()
            self.bg_music_backend = "kivy"

    def play_jump_sound(self):
        if self.jump_sound_fallback:
            self.jump_sound_fallback.play()
            return

        if self.jump_sound:
            self.jump_sound.stop()
            self.jump_sound.play()

    def spawn_pipe(self, dt):
        if not self.started:
            return

        gap_y = random.randint(150, 450)
        gap_size = 220

        bottom = Pipe(size=(60, gap_y - gap_size // 2), pos=(400, 0))
        top = Pipe(size=(60, 600 - (gap_y + gap_size // 2)), pos=(400, gap_y + gap_size // 2))

        self.pipes.append({"bottom": bottom, "top": top, "scored": False})
        self.add_widget(bottom)
        self.add_widget(top)

    def update(self, dt):
        if not self.started:
            return

        self.pipe_speed = min(
            self.max_pipe_speed,
            self.pipe_speed + self.speed_acceleration * dt
        )

        self.bird.velocity += self.gravity
        self.bird.y += self.bird.velocity

        for pipe in self.pipes:
            pipe["bottom"].x -= self.pipe_speed
            pipe["top"].x -= self.pipe_speed

        for pipe in self.pipes:
            if (self.bird.collide_widget(pipe["bottom"]) or
                    self.bird.collide_widget(pipe["top"])):
                self.reset()
                return

        if self.bird.y <= 0 or self.bird.top >= self.height:
            self.reset()
            return

        for pipe in self.pipes:
            if not pipe["scored"] and pipe["bottom"].right < self.bird.x:
                pipe["scored"] = True
                self.score += 1
                self.score_label.text = f"Score: {self.score}"
                if hasattr(self, 'app'):
                    self.app.storage.save_game_data({'score': self.score})

        remaining_pipes = []
        for pipe in self.pipes:
            bottom = pipe["bottom"]
            top = pipe["top"]
            if bottom.x > -60:
                remaining_pipes.append(pipe)
            else:
                self.remove_widget(bottom)
                self.remove_widget(top)
        self.pipes = remaining_pipes

    def reset(self):
        self.bird.pos = (100, 300)
        self.bird.velocity = 0
        self.score = 0
        self.score_label.text = "Score: 0"

        for pipe in self.pipes:
            self.remove_widget(pipe["bottom"])
            self.remove_widget(pipe["top"])

        self.pipes.clear()
        self.started = False
        self.pipe_speed = 1.5

        if self.start_btn.parent:
            self.remove_widget(self.start_btn)
        if not self.restart_btn.parent:
            self.add_widget(self.restart_btn)


# ============ APP ============
class FlappyApp(App):
    def build(self):
        self.storage = StorageAccess(self)
        self.storage.request_permissions()
        
        game = Game()
        game.app = self
        return game


if __name__ == "__main__":
    FlappyApp().run()