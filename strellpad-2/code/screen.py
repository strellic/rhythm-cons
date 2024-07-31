# sorry for the spaghetti
import adafruit_displayio_ssd1306
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font
from displayio import Bitmap
import displayio
import asyncio
import storage
import busio
import board
import json
import gc

import config

font = bitmap_font.load_font("fonts/spleen-5x8.bdf", Bitmap)
displayio.release_displays()

WIDTH = 128
HEIGHT = 32

DIR_LEFT = False
DIR_RIGHT = True

GRID_3x3 = 0
GRID_4x3 = 1

SELECT = 0
UP = 1
RIGHT = 2
LEFT = 3
DOWN = 4

def draw(pixels, color = 0xffffff):
    bitmap = displayio.Bitmap(WIDTH, HEIGHT, 2)
    palette = displayio.Palette(2)
    palette[0] = 0x000000
    palette[1] = color
    palette.make_transparent(0)
    tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
    group = displayio.Group()
    
    for p in pixels:
        if p[0] <= 0 or p[0] >= 128 or p[1] <= 0 or p[1] >= 32:
            continue 
        bitmap[p] = 1
    
    group.append(tile_grid)
    return group

class Screen:
    name = "base"
    def __init__(self):
        self.rerender_items = []
        self.rerender = False
        self.initial_render = True
    def render(self, items):
        if not self.initial_render:
            return
        for item in items:
            display.root_group.append(item)
    def update(self, renderable, items):
        for item in self.rerender_items:
            if renderable == item[0]:
                display.root_group.remove(item[1])
        self.rerender_items = [item for item in self.rerender_items if item[0] != renderable]
        for item in items:
            if item in display.root_group:
                continue
            display.root_group.append(item)
            self.rerender_items.append([renderable, item])
        if len(display.root_group) > 16:
            print("warning! the root group is starting to fill up! count:", len(display.root_group))
    def on_press(self, key):
        pass
    def on_switch_screen(self):
        pass
    def on_analog(self, x):
        pass
    def on_rotate(self, dir, velocity):
        pass

class Renderable:
    def __init__(self, **settings):
        self.can_select = False
        self.needs_render = True
        self.updates = settings.get("updates", False)
    def render(self, **settings):
        return []

class Text(Renderable):
    def __init__(self, text, **settings):
        super().__init__(**settings)
        self.text = text
        self.label = label.Label(font, text=self.text, color=0xFFFFFF, line_spacing=0.5, **settings)
    def render(self, **settings):
        for k, v in settings.items():
            setattr(self.label, k, v)
        self.label.text = self.text
        return [ self.label ]
    def change_text(self, text):
        if self.text != text:
            self.text = text
            self.needs_render = True

class Selectable(Text):
    def __init__(self, text, **settings):
        super().__init__(text, **settings)
        self.can_select = len(self.text) > 0
        self.updates = True
        self.on_select_handler = settings.get("on_select", lambda: None)
    def render(self, **settings):
        if self.can_select and settings["selected"]:
            settings["color"] = 0x000000
            settings["background_color"] = 0xFFFFFF
        else:
            settings["color"] = 0xFFFFFF
            settings["background_color"] = 0x000000
        return super().render(**settings)
    def on_press(self, key):
        if key == SELECT and self.can_select:
            self.on_select_handler()
    def change_text(self, text):
        if self.text != text:
            self.text = text
            self.needs_render = True
        self.can_select = len(self.text) > 0

class Toggle(Selectable):
    def __init__(self, options, start = 0, **settings):
        self.options = options
        self.index = start
        self.on_change_handler = settings.get("on_change", lambda v: v)
        self.format = settings.get("format", lambda s: str(s))
        super().__init__(self.format(options[start]), **settings)

    def render(self, **settings):
        self.change_text(self.format(self.options[self.index]))
        return super().render(**settings)
    
    def on_press(self, key):
        if key == SELECT:
            self.index += 1
            self.index %= len(self.options)
            self.on_change_handler(self.options[self.index])
            self.needs_render = True
    
    def change_index(self, index):
        if self.index != index:
            self.index = index
            self.needs_render = True

class Select(Selectable):
    def __init__(self, options, start = 0, wrap = False, **settings):
        self.options = options
        self.index = start
        self.wrap = wrap
        self.on_change_handler = settings.get("on_change", lambda v: v)
        self.format = settings.get("format", lambda s: str(s))
        super().__init__(self.format(options[start]), **settings)

    def render(self, **settings):
        self.change_text(self.format(self.options[self.index]))

        anchor_point, anchor_pos = settings["anchor_point"], settings["anchored_position"]
        dist_to_right_edge = (1 - anchor_point[0]) * 5 * len(self.text)
        dist_to_left_edge = anchor_point[0] * 5 * len(self.text)
        left_pos = round(anchor_pos[0] - dist_to_left_edge - 5)
        right_pos = round(anchor_pos[0] + dist_to_right_edge + 4)

        mid = round((0.5 - anchor_point[1]) * 7 + anchor_pos[1])

        pixels = []
        if self.can_select and (self.wrap or self.index - 1 >= 0):
            pixels += [(left_pos, mid), (left_pos + 1, mid - 1), (left_pos + 1, mid + 1)]
        if self.can_select and (self.wrap or self.index + 1 < len(self.options)):
            pixels += [(right_pos, mid), (right_pos - 1, mid - 1), (right_pos - 1, mid + 1)]
        if pixels:
            return [ draw(pixels) ] + super().render(**settings)
        return super().render(**settings)

    def on_rotate(self, dir, velocity):
        del velocity

        if dir == DIR_LEFT:
            if self.wrap and self.index - 1 == -1:
                self.index = len(self.options) - 1
            else:
                self.index = max(self.index - 1, 0)
        elif dir == DIR_RIGHT:
            if self.wrap and self.index + 1 >= len(self.options):
                self.index = 0
            else:
                self.index = min(self.index + 1, len(self.options) - 1)
        self.on_change_handler(self.options[self.index])
        self.needs_render = True
    
    def change_index(self, index):
        if index < 0 or index >= len(self.options):
            index = 0
        if self.index != index:
            self.index = index
            self.needs_render = True

    def change_options(self, options):
        if self.options != options:
            self.options = options
            self.needs_render = True
    
class NumSelect(Selectable):
    def __init__(
        self,
        start = 0,
        min = 0,
        max = 1,
        step = 1,
        wrap = False,
        velocity = lambda _: 1,
        **settings,
    ):
        self.value = start
        self.min = min
        self.max = max
        self.step = step
        self.wrap = wrap
        self.velocity = velocity
        self.format = settings.get("format", lambda s: str(s))
        self.on_change_handler = settings.get("on_change", lambda v: v)
        if isinstance(self.step, float):
            self.precision = len(str(self.step).split(".")[1])
        super().__init__(self.format(start), **settings)
    
    def render(self, **settings):
        self.change_text(self.format(self.value))

        anchor_point, anchor_pos = settings["anchor_point"], settings["anchored_position"]
        dist_to_right_edge = (1 - anchor_point[0]) * 5 * len(self.text)
        dist_to_left_edge = anchor_point[0] * 5 * len(self.text)
        left_pos = round(anchor_pos[0] - dist_to_left_edge - 5)
        right_pos = round(anchor_pos[0] + dist_to_right_edge + 4)

        mid = round((0.5 - anchor_point[1]) * 7 + anchor_pos[1])

        pixels = []
        if self.can_select and (self.wrap or self.value - self.step >= self.min):
            pixels += [(left_pos, mid), (left_pos + 1, mid - 1), (left_pos + 1, mid + 1)]
        if self.can_select and (self.wrap or self.value + self.step <= self.max):
            pixels += [(right_pos, mid), (right_pos - 1, mid - 1), (right_pos - 1, mid + 1)]
        if pixels:
            return [ draw(pixels) ] + super().render(**settings)
        return super().render(**settings)
    
    def on_rotate(self, dir, velocity):
        step = self.step * min(1, self.velocity(velocity))

        if dir == DIR_LEFT:
            if self.wrap and self.value - step < self.min:
                self.value = self.max
            else:
                self.value = max(self.min, self.value - step)
        elif dir == DIR_RIGHT:
            if self.wrap and self.value + step > self.max:
                self.value = self.min
            else:
                self.value = min(self.max, self.value + step)
        if isinstance(step, float):
            self.value = round(self.value, self.precision)
        self.on_change_handler(self.value)
        self.needs_render = True

    def change_value(self, value):
        if self.value != value:
            self.value = value
            self.needs_render = True

def velocity_profile(
    maximum_multiplier,
    velocity_threshold,
    velocity_cap,
):
    def handler(velocity):
        if velocity < velocity_threshold: return 1
        percentage = 1 - (
            velocity_cap - min(velocity, velocity_cap)
        ) / (velocity_cap - velocity_threshold)
        return 1 + percentage * max(0, maximum_multiplier - 1)
    return handler

percentage_velocity = velocity_profile(10, 3, 7)

areas3x3 = [
    ((0, 0), (7,0)),
    ((0.5, 0), (WIDTH // 2, 0)),
    ((1, 0), (WIDTH - 7, 0)),

    ((0, 0.5), (7, HEIGHT // 2)),
    ((0.5, 0.5), (WIDTH // 2, HEIGHT // 2)),
    ((1, 0.5), (WIDTH - 7, HEIGHT // 2)),

    ((0, 1), (7, HEIGHT)),
    ((0.5, 1), (WIDTH // 2, HEIGHT)),
    ((1, 1), (WIDTH - 7, HEIGHT))
]
areas4x3 = [
    ((0, 0), (7,0)),
    ((0.5, 0), (WIDTH // 2, 0)),
    ((1, 0), (WIDTH - 7, 0)),

    ((0, 0.5), (7, 4 * HEIGHT // 10)),
    ((0.5, 0.5), (WIDTH // 2, 4 * HEIGHT // 10)),
    ((1, 0.5), (WIDTH - 7, 4 * HEIGHT // 10)),

    ((0, 0.5), (7, 6 * HEIGHT // 10)),
    ((0.5, 0.5), (WIDTH // 2, 6.25 * HEIGHT // 10)),
    ((1, 0.5), (WIDTH - 7, 6 * HEIGHT // 10)),

    ((0, 1), (7, HEIGHT)),
    ((0.5, 1), (WIDTH // 2, HEIGHT)),
    ((1, 1), (WIDTH - 7, HEIGHT))
]
areas = [areas3x3, areas4x3]

class GridScreen(Screen):
    def __init__(self, items, mode = GRID_3x3, start = 0):
        super().__init__()
        self.items = items
        self.areas = areas[mode]
        self.global_rerender = False

        if len(self.items) != len(self.areas):
            raise Exception("unable to render grid with incorrect number of items")

        self.index = start
    def on_render(self):
        if self.global_rerender:
            for _, item in display.screen.rerender_items:
                display.root_group.remove(item)
            display.screen.rerender_items = []
        
        for i in range(len(self.items)):
            if self.items[i] == None:
                continue

            settings = {}
            settings["anchor_point"], settings["anchored_position"] = self.areas[i]
            settings["selected"] = self.index == i

            if self.items[i].updates and (self.global_rerender or self.items[i].needs_render):
                self.update(self.items[i], self.items[i].render(**settings))
                self.items[i].needs_render = False
            elif self.initial_render:
                self.render(self.items[i].render(**settings))
        self.global_rerender = False
    def on_rotate(self, dir, velocity):
        item = self.items[self.index]
        if item != None and hasattr(item, "on_rotate"):
            item.on_rotate(dir, velocity)
    def on_press(self, key):
        item = self.items[self.index]
        if item != None and hasattr(item, "on_press"):
            item.on_press(key)

        prev_index = self.index

        # UP:
        # if we are on the top row, do nothing
        # check if the item above exists and is can_select
        # else, start at the previous row and find the next can_select item moving up and to the left
        if key == UP:
            if self.index < 3:
                return
            if self.items[self.index - 3] != None and self.items[self.index - 3].can_select:
                self.index = self.index - 3
            else:
                for i in range((self.index // 3) * 3 - 1, -1, -1):
                    if self.items[i] != None and self.items[i].can_select:
                        self.index = i
                        break
        # DOWN:
        # if we are on the bottom row, do nothing
        # check if the item below exists and is can_select
        # else, start at the next row and find the next can_select item moving down and to the right
        elif key == DOWN:
            if self.index + 3 >= len(self.items):
                return
            if self.items[self.index + 3] != None and self.items[self.index + 3].can_select:
                self.index = self.index + 3
            else:
                for i in range((self.index // 3) * 3 + 3, len(self.items)):
                    if self.items[i] != None and self.items[i].can_select:
                        self.index = i
                        break
        
        # LEFT:
        # if we are on the left column, do nothing
        # then, move left along the current row until you hit either the end or a can_select item
        elif key == LEFT:
            if self.index % 3 == 0:
                return
            for i in range(self.index - 1, (self.index // 3) * 3 - 1, -1):
                if self.items[i] != None and self.items[i].can_select:
                    self.index = i
                    break

        # RIGHT:
        # if we are on the right column, do nothing
        # then, move right along the current row until you hit either the end or a can_select item
        elif key == RIGHT:
            if self.index % 3 == 2:
                return
            for i in range(self.index + 1, (self.index // 3) * 3 + 3):
                if self.items[i] != None and self.items[i].can_select:
                    self.index = i
                    break

        if self.index != prev_index:
            self.global_rerender = True

    def change_index(self, new_index):
        if self.index != new_index:
            self.index = new_index
            self.global_rerender = True

i2c = busio.I2C(board.GP1, board.GP0)

display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT, auto_refresh=False)
display.root_group = draw([])
display.refresh()

def switch_screen(screen):
    if hasattr(display, "screen"):
        display.screen.on_switch_screen()
    screen.rerender = True
    display.screen = screen
    display.root_group = displayio.Group()

class DebugScreen(GridScreen):
    name = "debug"
    def __init__(self):
        self.sw1 = Text("sw 1: 0", updates=True)
        self.sw2 = Text("sw 2: 0", updates=True)
        self.sw3 = Text("sw 3: 0", updates=True)
        self.sw4 = Text("sw 4: 0", updates=True)
        self.free_mem = Text("free mem: 0", updates=True)
        super().__init__([
            self.sw1, None, self.sw2,
            self.sw3, None, self.sw4,
            self.free_mem, None, Text("play")
        ])

    def on_analog(self, values):
        self.sw1.change_text(f"sw 1: {values[0]}")
        self.sw2.change_text(f"sw 2: {values[1]}")
        self.sw3.change_text(f"sw 3: {values[2]}")
        self.sw4.change_text(f"sw 4: {values[3]}")
        self.rerender = True
    
    def on_render(self):
        self.free_mem.change_text(f"free mem: {gc.mem_free()}")
        super().on_render()

    def on_press(self, key):
        if key == RIGHT:
            switch_screen(PlayScreen())
        elif key == SELECT:
            switch_screen(DebugEditScreen())

class DebugEditScreen(GridScreen):
    name = "debug_edit"
    def __init__(self):
        def boot_into_usb_mode():
            config.config_data["usb_drive"] = True
            config.save()
            import microcontroller
            microcontroller.reset()
        
        def wipe_mem():
            with open("config.json", "w") as f:
                f.write(json.dumps(config.default_data))
            import microcontroller
            microcontroller.reset()

        usb_mode = Selectable("boot into usb mode", on_select=boot_into_usb_mode)
        wipe_mem = Selectable("wipe device memory", on_select=wipe_mem)
        exit_debug = Selectable("exit debug menu", on_select=lambda: switch_screen(DebugScreen()))

        super().__init__([
            None, usb_mode, None,
            None, wipe_mem, None,
            None, exit_debug, None
        ], GRID_3x3, start=7)

class PlayScreen(GridScreen):
    name = "play"
    def __init__(self):
        status = None
        if all(c == [0,0] for c in config.data.calibration):
            status = Text("calibration required")

        # we booted successfully! reset the boot count here
        config.config_data["boot_cnt"] = 0
        config.save()

        super().__init__([
            None, Text("strellpad"), None,
            None, status, None,
            Text("debug"), None, Text("settings")
        ])
    def on_press(self, key):
        if key == LEFT:
            switch_screen(DebugScreen())
        elif key == RIGHT:
            switch_screen(SettingsScreen())
    
class SettingsScreen(GridScreen):
    name = "settings"
    def __init__(self):
        self.actuation = config.data.actuation
        self.key_brightness = config.data.key_brightness
        self.edge_brightness = config.data.edge_brightness

        actuation = NumSelect(
            self.actuation,
            min=0.01,
            max=1,
            step=0.01,
            velocity=percentage_velocity,
            format=lambda v: f"actuation: {round(v * 100)}%",
            on_change=lambda v: setattr(self, "actuation", v)
        )
        key_brightness = NumSelect(
            self.key_brightness,
            min=0.01,
            max=1,
            step=0.01,
            velocity=percentage_velocity,
            format=lambda v: f"key brightness: {round(v * 100)}%",
            on_change=lambda v: setattr(self, "key_brightness", v),
        )
        edge_brightness = NumSelect(
            self.edge_brightness,
            min=0.01,
            max=1,
            step=0.01,
            velocity=percentage_velocity,
            format=lambda v: f"edge brightness: {round(v * 100)}%",
            on_change=lambda v: setattr(self, "edge_brightness", v),
        )

        super().__init__([
            None, actuation, None,
            None, key_brightness, None,
            None, edge_brightness, None,
            Text("play"), None, Text("settings 2")
        ], GRID_4x3, start=1)

    def on_switch_screen(self):
        if self.actuation != config.data.actuation:
            config.data.actuation = round(self.actuation, 2)
            config.save()
        if self.key_brightness != config.data.key_brightness:
            config.data.key_brightness = round(self.key_brightness, 2)
            config.save()
        if self.edge_brightness != config.data.edge_brightness:
            config.data.edge_brightness = round(self.edge_brightness, 2)
            config.save()

    def on_press(self, key):
        if key == LEFT:
            switch_screen(PlayScreen())
        elif key == RIGHT:
            switch_screen(Settings2Screen())
        else:
            super().on_press(key)

class Settings2Screen(GridScreen):
    name = "settings2"
    def __init__(self):
        self.reactive_edge = config.data.reactive_edge
        self.reactive_time = config.data.reactive_time
        self.enc_hold_time = config.data.enc_hold_time

        reactive_edge = Toggle([False, True], int(self.reactive_edge), format=lambda v: f"reactive edge: {'on' if v else 'off'}", on_change=lambda v: setattr(self, "reactive_edge", v))
        reactive_time = NumSelect(self.reactive_time, min=0.1, max=float('inf'), step=0.1, format=lambda v: f"reactive time: {round(v, 1)}s", on_change=lambda v: setattr(self, "reactive_time", v))
        enc_hold_time = NumSelect(self.enc_hold_time, min=0.1, max=float('inf'), step=0.1, format=lambda v: f"knob hold time: {round(v, 1)}s", on_change=lambda v: setattr(self, "enc_hold_time", v))

        super().__init__([
            None, reactive_edge, None,
            None, reactive_time, None,
            None, enc_hold_time, None,
            Text("settings"), None, Text("settings 3")
        ], GRID_4x3, start=1)

    def on_switch_screen(self):
        if self.reactive_edge != config.data.reactive_edge:
            config.data.reactive_edge = self.reactive_edge
            config.save()
        if self.reactive_time != config.data.reactive_time:
            config.data.reactive_time = round(self.reactive_time, 1)
            config.save()
        if self.enc_hold_time != config.data.enc_hold_time:
            config.data.enc_hold_time = round(self.enc_hold_time, 1)
            config.save()
    
    def on_press(self, key):
        if key == LEFT:
            switch_screen(SettingsScreen())
        elif key == RIGHT:
            switch_screen(Settings3Screen())
        else:
            super().on_press(key)

class Settings3Screen(GridScreen):
    name = "settings3"
    def __init__(self):
        self.mode = config.data.mode
        options = ["keypad", "gamepad"]

        mode = Toggle(options, options.index(self.mode), format=lambda v: f"mode: {v}", on_change=lambda v: setattr(self, "mode", v))

        super().__init__([
            None, mode, None,
            None, None, None,
            None, None, None,
            Text("settings 2"), None, Text("profiles")
        ], GRID_4x3, start=1)

    def on_switch_screen(self):
        if self.mode != config.data.mode:
            config.data.mode = self.mode
            config.save()
    
    def on_press(self, key):
        if key == LEFT:
            switch_screen(Settings2Screen())
        elif key == RIGHT:
            switch_screen(ProfileScreen())
        else:
            super().on_press(key)

class ProfileScreen(GridScreen):
    name = "profile"
    def __init__(self):
        self.profile_names = [p["name"] for p in config.config_data["profiles"]]
        self.active_profile = config.config_data["active_profile"]
        
        def on_profile_change(profile):
            self.active_profile = self.profile_names.index(profile)
            config.change_profile(self.active_profile)
            config.edge_anim = config.load_anim(*config.data.edge_anim)

        def on_delete():
            config.config_data["profiles"].pop(self.active_profile)
            self.active_profile -= 1
            config.change_profile(self.active_profile)
            self.profile_names = [p["name"] for p in config.config_data["profiles"]]
            self.profile.options = self.profile_names
            self.profile.change_index(self.active_profile)
            config.edge_anim = config.load_anim(*config.data.edge_anim)

        self.profile = Select(self.profile_names, self.active_profile, on_change=on_profile_change, format=lambda v: f"profile: {v}")
        self.new = Selectable("new", on_select=lambda: switch_screen(NewProfileScreen()))
        self.delete = Selectable("delete", on_select=on_delete)

        super().__init__([
            None, self.profile, None,
            None, self.new, None,
            None, self.delete, None,
            Text("settings 3"), None, Text("RT")
        ], GRID_4x3, 1)

    def on_press(self, key):
        if key == LEFT:
            switch_screen(Settings3Screen())
        elif key == RIGHT:
            switch_screen(RTScreen())
        else:
            super().on_press(key)
    
    def on_render(self):
        self.delete.change_text("delete" if self.active_profile > 0 else "") 
        super().on_render()

profile_alphabet = [c for c in "abcdefghijklmnopqrstuvwxyz -_"]
class NewProfileScreen(GridScreen):
    name = "new_profile"
    def __init__(self):
        self.alphabet_index = 0
        self.name = ""

        def on_plus():
            self.name.change_text(self.name.text + profile_alphabet[self.alphabet_index])
        def on_minus():
            self.name.change_text(self.name.text[:-1])
        def on_finish():
            if len(self.name.text) != 0:
                data = json.loads(json.dumps(config.config_data["profiles"][0]))
                data["name"] = self.name.text
                config.config_data["profiles"].append(data)
                config.active_profile = len(config.config_data["profiles"]) - 1
                config.data = config.Config(data)
                config.save()
            switch_screen(ProfileScreen())

        self.alphabet = Select(profile_alphabet, self.alphabet_index, on_change=lambda v: setattr(self, "alphabet_index", profile_alphabet.index(v)), wrap=True)
        self.minus = Selectable("-", on_select=on_minus)
        self.plus = Selectable("+", on_select=on_plus)
        self.finish = Selectable("finish", on_select=on_finish)
        self.name = Text("", updates=True)

        super().__init__([
            None, Text("enter name:"), None,
            None, self.name, None,
            None, self.alphabet, None,
            self.minus, self.finish, self.plus
        ], GRID_4x3, 7)

    def on_render(self):
        self.plus.change_text("+" if len(self.name.text) < 12 else "")
        self.minus.change_text("-" if len(self.name.text) > 0 else "")
        self.finish.change_text("cancel" if len(self.name.text) == 0 else "finish")
        super().on_render()

class RTScreen(GridScreen):
    name = "rapid_trigger"
    def __init__(self):
        self.rapid_trigger = config.data.rapid_trigger
        self.continuous_rt = config.data.continuous_rapid_trigger
        self.rt_area = config.data.rt_area

        rapid_trigger = Toggle([False, True], int(self.rapid_trigger), format=lambda v: f"rapid trigger: {'on' if v else 'off'}", on_change=lambda v: setattr(self, "rapid_trigger", v))
        continuous_rt = Toggle([False, True], int(self.continuous_rt), format=lambda v: f"continuous RT: {'on' if v else 'off'}", on_change=lambda v: setattr(self, "continuous_rt", v))
        rt_area = NumSelect(self.rt_area, min=0, max=1, step=0.01, format=lambda v: f"RT area: {round(self.rt_area * 100)}%", on_change=lambda v: setattr(self, "rt_area", v))

        super().__init__([
            None, rapid_trigger, None,
            None, continuous_rt, None,
            None, rt_area, None,
            Text("profiles"), None, Text("calibration")
        ], GRID_4x3, start=1)
    
    def on_switch_screen(self):
        if self.rapid_trigger != config.data.rapid_trigger:
            config.data.rapid_trigger = self.rapid_trigger
            config.save()
        if self.continuous_rt != config.data.continuous_rapid_trigger:
            config.data.continuous_rapid_trigger = self.continuous_rt
            config.save()
        if self.rt_area != config.data.rt_area:
            config.data.rt_area = round(self.rt_area, 2)
            config.save()
    
    def on_press(self, key):
        if key == LEFT:
            switch_screen(ProfileScreen())
        elif key == RIGHT:
            switch_screen(CalibrationSelectScreen())
        else:
            super().on_press(key)

class CalibrationSelectScreen(GridScreen):
    name = "calibration_select"
    def __init__(self, switch_no = 1):
        self.switch_no = switch_no
        switch_no = NumSelect(self.switch_no, 1, 4, format=lambda v: f"calibrate switch #{v}", on_change=lambda v: setattr(self, "switch_no", v))
        start = Selectable("start calibration", on_select=lambda: switch_screen(CalibrationScreen(self.switch_no)))
        super().__init__([
            None, switch_no, None,
            None, start, None,
            Text("rapid trigger"), None, Text("input")
        ], GRID_3x3, start=1)

    def on_press(self, key):
        if key == LEFT:
            switch_screen(RTScreen())
        elif key == RIGHT:
            switch_screen(InputSelectScreen())
        else:
            super().on_press(key)

class CalibrationScreen(GridScreen):
    def __init__(self, switch_no):
        self.switch_no = switch_no
        self.state = 0

        self.base = -1
        self.pressed = -1
        self.analog_val = -1

        self.l1 = Text("with switch at rest,", updates=True)
        self.l2 = Text("press SELECT", updates=True)

        super().__init__([
            None, Text(f"calibrating switch {self.switch_no}"), None,
            None, self.l1, None,
            None, self.l2, None
        ])
    
    def on_analog(self, values):
        self.analog_val = values[self.switch_no - 1]

    def on_press(self, key):
        if key == SELECT:
            if self.state == 0:
                self.base = self.analog_val
                self.state = 1
                self.l1.change_text("with switch pressed,")
            elif self.state == 1:
                self.pressed = self.analog_val
                if abs((self.base - self.pressed) / float(self.base)) <= 0.10:
                    self.state = 2
                    self.l1.change_text("calibration failed")
                else:
                    self.state = 3
                    self.l1.change_text("calibration completed")
                self.l2.change_text("press SELECT to return")
            else:
                if self.state == 3:
                    config.data.calibration[self.switch_no - 1] = [self.base, self.pressed]
                    config.save()
                switch_screen(CalibrationSelectScreen(self.switch_no))

class InputSelectScreen(GridScreen):
    name = "input_select"
    def __init__(self, switch_no = 1):
        if config.data.mode == "keypad":
            self.switch_no = switch_no
            types = ["??", "switch #1", "switch #2", "switch #3", "switch #4", "knob left", "knob right", "knob press", "knob hold"]
            switch_no = NumSelect(self.switch_no, 1, 8, format=lambda v: f"edit {types[v]} input", on_change=lambda v: setattr(self, "switch_no", v))
            start = Selectable("start edit", on_select=lambda: switch_screen(InputScreen(self.switch_no)))
            super().__init__([
                None, switch_no, None,
                None, start, None,
                Text("calibration"), None, Text("colors")
            ], GRID_3x3, start=1)
        else:
            super().__init__([
                None, Text("input editing disabled"), None,
                None, Text("due to gamepad mode"), None,
                Text("calibration"), None, Text("colors")
            ], GRID_3x3, start=1)

    def on_press(self, key):
        if key == LEFT:
            switch_screen(CalibrationSelectScreen())
        elif key == RIGHT:
            switch_screen(ColorSelectScreen())
        else:
            super().on_press(key)

# add more keys here if you want to be able to choose them
alphabet = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [
    "ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
    "SPACE", "ENTER", "ESCAPE", "UP_ARROW", "LEFT_ARROW", "RIGHT_ARROW", "DOWN_ARROW",
    "SHIFT", "RIGHT_SHIFT", "DELETE", "CTRL", "RIGHT_CTRL", "ALT", "RIGHT_ALT", "PRINT_SCRN",

    # consumer control codes
    "BRIGHT_DEC", "BRIGHT_INC", "PLAY_PAUSE", "STOP", "MUTE", "PREV_TRACK", "NEXT_TRACK",
    "VOLUME_DEC", "VOLUME_INC"
]

# handle fixup names as well as failure case if key name changed
def key_to_char_index(key):
    try:
        return alphabet.index(key)
    except:
        for i in range(len(alphabet)):
            if key == fixup_key_name(alphabet[i]):
                return i
        return 0
    
# the alphabet names in screen.py have to be short enough to be displayed
# this fixes them up so they are the same as the ones in Keycode / ConsumerControlCode
def fixup_key_name(key):
    key = key.replace("DEC", "DECREMENT")
    key = key.replace("INC", "INCREMENT")
    key = key.replace("PREV", "PREVIOUS")
    key = key.replace("CTRL", "CONTROL")
    key = key.replace("SCRN", "SCREEN")
    key = key.replace("BRIGHTNESS", "BRIGHT")
    if key == "NEXT_TRACK" or key == "PREVIOUS_TRACK":
        key = "SCAN_" + key
    return key

class InputScreen(GridScreen):
    name = "input"
    def __init__(self, switch_no):
        self.switch_no = switch_no
        self.has_duration = self.switch_no > 6

        # we need to deepcopy this so that we get a separate reference to not modify the original
        # there is no copy.deepcopy so we just use json
        self.keys = json.loads(json.dumps(config.data.keys[self.switch_no - 1] if self.switch_no <= 6 else config.data.enc_keys[self.switch_no - 7]))
        self.key_index = 0

        self.char_index = key_to_char_index(self.keys[self.key_index] if not self.has_duration else self.keys[self.key_index][0])

        def on_save():
            if not self.has_duration:
                config.data.keys[self.switch_no - 1] = [fixup_key_name(k) for k in self.keys]
            else:
                config.data.enc_keys[self.switch_no - 7] = [[fixup_key_name(k[0]), k[1]] for k in self.keys]
            config.save()
            switch_screen(InputSelectScreen(self.switch_no))

        self.types = ["??", "switch #1:", "switch #2:", "switch #3:", "switch #4:", "knob left:", "knob right:", "knob press:", "knob hold:"]
        self.cancel = Selectable("cancel", on_select=lambda: switch_screen(InputSelectScreen(self.switch_no)))
        self.save = Selectable("save", on_select=on_save)

        # these need to change index because next / prev / delete might disappear on key index change
        def on_new_next():
            if self.key_index + 1 >= len(self.keys):
                if not self.has_duration:
                    self.keys.append("A")
                else:
                    self.keys.append(["A", 0])
            
            self.key_index += 1
            self.char_index = key_to_char_index(self.keys[self.key_index] if not self.has_duration else self.keys[self.key_index][0])
            self.change_index(4)
        
        def on_prev():
            self.key_index -= 1
            self.char_index = key_to_char_index(self.keys[self.key_index] if not self.has_duration else self.keys[self.key_index][0])
            self.change_index(4)

        def on_delete():
            self.keys.pop(self.key_index)
            self.key_index -= 1
            self.char_index = key_to_char_index(self.keys[self.key_index] if not self.has_duration else self.keys[self.key_index][0])
            self.change_index(4)

        def on_alphabet_change(v):
            if not self.has_duration:
                self.keys[self.key_index] = v
            else:
                self.keys[self.key_index][0] = v
            self.char_index = key_to_char_index(self.keys[self.key_index] if not self.has_duration else self.keys[self.key_index][0])

        def on_duration_change(v):
            self.keys[self.key_index][1] = v

        self.new_next = Selectable("next", on_select=on_new_next)
        self.prev = Selectable("", on_select=on_prev)
        self.delete = Selectable("", on_select=on_delete)

        self.index_text = Text(f"key #{self.key_index + 1}", updates=True)

        if not self.has_duration:
            self.alphabet = Select(alphabet, key_to_char_index(self.keys[self.key_index]), on_change=on_alphabet_change, wrap=True)
            super().__init__([
                Text(self.types[self.switch_no]), None, self.index_text,
                self.prev, self.alphabet, self.new_next,
                self.cancel, self.delete, self.save
            ], GRID_3x3, start=4)
        else:
            self.alphabet = Select(alphabet, key_to_char_index(self.keys[self.key_index][0]), on_change=on_alphabet_change, wrap=True)
            self.duration = NumSelect(self.keys[self.key_index][1], min=0, max=10, step=0.1, format=lambda s: f"duration: {round(s, 1)}s", on_change=on_duration_change)
            super().__init__([
                Text(self.types[self.switch_no]), None, self.index_text,
                self.prev, self.alphabet, self.new_next,
                None, self.duration, None,
                self.cancel, self.delete, self.save
            ], GRID_4x3, start=4)
    
    def on_render(self):
        self.index_text.change_text(f"key #{self.key_index + 1}")
        self.alphabet.change_index(self.char_index)
        self.prev.change_text("prev" if self.key_index - 1 >= 0 else "")
        self.new_next.change_text("new" if self.key_index + 1 >= len(self.keys) else "next")
        self.delete.change_text("delete" if self.key_index > 0 else "")

        if self.has_duration:
            self.duration.change_value(self.keys[self.key_index][1])

        super().on_render()

class ColorSelectScreen(GridScreen):
    name = "color_select"
    def __init__(self, switch_no = 1):
        self.switch_no = switch_no
        types = ["??", "switch #1", "switch #2", "switch #3", "switch #4", "edge"]
        switch_no = NumSelect(self.switch_no, 1, 5, format=lambda v: f"edit {types[v]} color", on_change=lambda v: setattr(self, "switch_no", v))
        start = Selectable("start edit", on_select=lambda: switch_screen(ColorScreen(self.switch_no)))
        super().__init__([
            None, switch_no, None,
            None, start, None,
            Text("input"), None, Text("edge leds")
        ], GRID_3x3, start=1)
    
    def on_press(self, key):
        if key == LEFT:
            switch_screen(InputSelectScreen())
        elif key == RIGHT:
            switch_screen(EdgeLightsScreen())
        else:
            super().on_press(key)

class ColorScreen(GridScreen):
    name = "color"
    def __init__(self, switch_no):
        self.switch_no = switch_no

        types = ["??", "switch #1", "switch #2", "switch #3", "switch #4", "edge"]
        def set_color(index, v):
            config.data.color[switch_no - 1][index] = v

        def on_save():
            config.save()
            switch_screen(ColorSelectScreen(switch_no))

        save = Selectable("save", on_select=on_save)

        self.r = NumSelect(config.data.color[switch_no - 1][0], min=0, max=255, step=1, wrap=True, format=lambda v: f"R: {v}", on_change=lambda v: set_color(0, v))
        self.g = NumSelect(config.data.color[switch_no - 1][1], min=0, max=255, step=1, wrap=True, format=lambda v: f"G: {v}", on_change=lambda v: set_color(1, v))
        self.b = NumSelect(config.data.color[switch_no - 1][2], min=0, max=255, step=1, wrap=True, format=lambda v: f"B: {v}", on_change=lambda v: set_color(2, v))

        def on_toggle(v):
            if v == "enable":
                config.data.color[switch_no - 1] = [0,0,0]
            else:
                config.data.color[switch_no - 1] = [255, 255, 255]
            self.r.change_value(config.data.color[switch_no - 1][0])
            self.g.change_value(config.data.color[switch_no - 1][1])
            self.b.change_value(config.data.color[switch_no - 1][2])

        self.toggle = Toggle(["disable", "enable"], int(all(c == 0 for c in config.data.color[switch_no - 1])), on_change=on_toggle)

        super().__init__([
            None, Text(f"{types[switch_no]} colors"), None,
            self.r, self.g, self.b,
            self.toggle, None, save
        ], GRID_3x3, start=3)

    def on_switch_screen(self):
        for i in range(len(config.edge_pixels)):
            config.edge_pixels[i] = (0, 0, 0)
        config.edge_pixels.show()
        config.edge_anim = config.load_anim(*config.data.edge_anim)
        for i in range(len(config.key_pixels)):
            config.key_pixels[i] = (0, 0, 0)
        config.key_pixels.show()
    
    def on_render(self):
        if self.switch_no == 5:
            for i in range(len(config.edge_pixels)):
                config.edge_pixels[i] = config.data.color[self.switch_no - 1]
            config.edge_pixels.show()
        else:
            config.key_pixels[self.switch_no - 1] = config.data.color[self.switch_no - 1]
            config.key_pixels.show()
        self.r.change_value(config.data.color[self.switch_no - 1][0])
        self.g.change_value(config.data.color[self.switch_no - 1][1])
        self.b.change_value(config.data.color[self.switch_no - 1][2])
        self.toggle.change_index(int(all(c == 0 for c in config.data.color[self.switch_no - 1])))
        super().on_render()

class EdgeLightsScreen(GridScreen):
    name = "edge_lights"
    def __init__(self):
        super().__init__([
            None, Text("edge leds"), None,
            None, Selectable("start edit", on_select=lambda: switch_screen(EdgeLightsConfigureScreen())), None,
            Text("colors"), None, None
        ], GRID_3x3, start=4)
    
    def on_press(self, key):
        if key == LEFT:
            switch_screen(ColorSelectScreen())
        else:
            super().on_press(key)

class EdgeLightsConfigureScreen(GridScreen):
    name = "edge_lights_configure"
    def __init__(self):
        self.anim_modes = list(config.anim_map.keys())
        self.anim_type = config.data.edge_anim[0]
        self.anim_args = [a for a in config.anim_args_map[self.anim_type] if isinstance(a, tuple)]
        self.anim_vals = config.data.edge_anim[1][:]
        self.edge_anim = config.load_anim(*config.data.edge_anim)

        self.arg_index = 0
        self.type_index = self.anim_modes.index(self.anim_type)

        def set_arg_value(v):
            self.anim_vals[self.arg_index] = v
            self.edge_anim = config.load_anim(self.anim_type, self.anim_vals)

        def on_mode_change(v):
            self.type_index = self.anim_modes.index(v)
            self.anim_type = self.anim_modes[self.type_index]
            self.anim_args = [a for a in config.anim_args_map[self.anim_type] if isinstance(a, tuple)]
            self.anim_vals = [a[1] for a in config.anim_args_map[self.anim_type] if isinstance(a, tuple)]
            self.edge_anim = config.load_anim(self.anim_type, self.anim_vals)
            self.arg_index = 0

        self.mode = Select(self.anim_modes, self.type_index, on_change=on_mode_change)
        self.arg = NumSelect(0, 0, 0, 0, format=lambda v: "", on_change=set_arg_value)

        def on_prev():
            self.arg_index -= 1

        def on_next():
            self.arg_index += 1

        def on_finish():
            config.edge_anim = self.edge_anim
            on_cancel()
        
        def on_cancel():
            switch_screen(EdgeLightsScreen())
            for i in range(len(config.edge_pixels)):
                config.edge_pixels[i] = (0, 0, 0)
            config.edge_pixels.show()

        self.prev = Selectable("", on_select=on_prev)
        self.next = Selectable("", on_select=on_next)
        self.finish = Selectable("finish", on_select=on_finish)
        self.cancel = Selectable("cancel", on_select=on_cancel)

        super().__init__([
            None, self.mode, None,
            None, self.arg, None,
            self.prev, None, self.next,
            self.cancel, None, self.finish
        ], GRID_4x3, start=1)
    
    def update_anim(self):
        self.edge_anim.animate()
    
    def on_render(self):
        self.next.change_text("next" if self.arg_index + 1 < len(self.anim_args) else "")
        self.prev.change_text("prev" if self.arg_index - 1 >= 0 else "")

        if len(self.anim_args) > 0:
            self.arg.min, self.arg.max, self.arg.step = self.anim_args[self.arg_index][2:]
            if isinstance(self.arg.step, float):
                self.arg.precision = len(str(self.arg.step).split(".")[1])
            self.arg.format = lambda v: f"{self.anim_args[self.arg_index][0]}: {v}"
            self.arg.change_value(self.anim_vals[self.arg_index])
        else:
            self.arg.format = lambda v: ""
            self.arg.change_value("")

        super().on_render()

class USBScreen(GridScreen):
    def __init__(self):
        super().__init__([
            None, Text("USB Mode"), None,
            None, Text("to reboot,"), None,
            None, Text("press SELECT"), None,
        ], GRID_3x3)
    def on_press(self, key):
        if key == SELECT:
            import microcontroller
            microcontroller.reset()

switch_screen(USBScreen() if storage.getmount("/").readonly else PlayScreen())
async def run():
    while True:
        if display.screen.rerender:
            display.screen.rerender = False
            for renderable, item in display.screen.rerender_items:
                if renderable.needs_render:
                    display.root_group.remove(item)
            display.screen.rerender_items = [v for v in display.screen.rerender_items if not v[0].needs_render]
            display.screen.on_render()
            display.screen.initial_render = False
            display.refresh()
            gc.collect()
        await asyncio.sleep(0)

def on_press(key_number):
    display.screen.on_press(key_number)
    display.screen.rerender = True

def on_rotate(direction, velocity):
    display.screen.on_rotate(direction, velocity)
    display.screen.rerender = True

def on_analog(values):
    display.screen.on_analog(values)



