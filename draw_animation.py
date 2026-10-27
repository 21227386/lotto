"""Perspective-projected 3D lottery drum, software rendered with Tk Canvas."""
import math
import random
import tkinter as tk
from tkinter import ttk
from scene3d import rotate_point, project_point, advance_particle


def ball_color(number):
    return '#e9b51f' if number <= 10 else '#2980c7' if number <= 20 else '#dc4d55' if number <= 30 else '#687585' if number <= 40 else '#39945c'


def shade(color, factor):
    return '#' + ''.join(f'{min(255, max(0, int(int(color[i:i + 2], 16) * factor))):02x}' for i in (1, 3, 5))


class Sphere:
    """Layered lighting and specular highlights for a billboarded 3D ball."""
    def __init__(self, canvas, number):
        self.canvas = canvas
        self.number = number
        self.layers = [canvas.create_oval(0, 0, 0, 0, outline='') for _ in range(5)]
        self.glint = canvas.create_oval(0, 0, 0, 0, fill='#ffffff', outline='')
        self.text = canvas.create_text(0, 0, fill='white', font=('Times New Roman', 10, 'bold'))
        self.items = self.layers + [self.glint, self.text]

    def draw(self, x, y, radius, light=1.0, number=None):
        if number is not None:
            self.number = number
        color = ball_color(self.number)
        for index, item in enumerate(self.layers):
            shrink = 1 - index * 0.13
            offset = index * radius * 0.055
            r = radius * shrink
            self.canvas.coords(item, x - offset - r, y - offset - r, x - offset + r, y - offset + r)
            self.canvas.itemconfigure(item, fill=shade(color, light * (0.57 + index * 0.17)), state='normal')
        self.canvas.coords(self.glint, x - radius * 0.50, y - radius * 0.65, x - radius * 0.10, y - radius * 0.38)
        self.canvas.itemconfigure(self.glint, state='normal')
        self.canvas.coords(self.text, x, y + radius * 0.10)
        self.canvas.itemconfigure(self.text, text=f'{self.number:02d}', font=('Times New Roman', max(7, int(radius * 0.80)), 'bold'), state='normal')
        for item in self.items:
            self.canvas.tag_raise(item)

    def hide(self):
        for item in self.items:
            self.canvas.itemconfigure(item, state='hidden')


class LottoMachine(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, width=340, height=365, bg='#0a1429', highlightthickness=0)
        self.canvas.pack()
        c = self.canvas
        c.create_text(170, 22, text='3D LOTTO DRAW', fill='#eff9ff', font=('Times New Roman', 17, 'bold'))
        for i in range(8):
            c.create_oval(46 + i, 38 + i, 294 - i, 286 - i, fill=shade('#183b58', 0.5 + i * 0.065), outline='')
        c.create_oval(62, 54, 278, 270, fill='#102238', outline='#7eacbf', width=2)
        self.rings = [c.create_line(0, 0, 1, 1, fill='#365b72', width=1, smooth=True) for _ in range(7)]
        c.create_polygon(124, 263, 151, 263, 135, 318, 110, 318, fill='#213f59', outline='#64869c')
        c.create_polygon(189, 263, 216, 263, 230, 318, 205, 318, fill='#142d46', outline='#64869c')
        c.create_polygon(90, 322, 250, 322, 264, 336, 76, 336, fill='#294862', outline='#8ca7b7')
        c.create_rectangle(76, 336, 264, 342, fill='#12283f', outline='')
        c.create_oval(125, 321, 216, 333, fill='#050d1a', outline='')
        self.caption = c.create_text(170, 353, text='READY', fill='#b6cbe0', font=('Times New Roman', 11))
        self.output = Sphere(c, 1)
        self.output.draw(170, 302, 25)
        c.itemconfigure(self.output.text, text='—')
        self.particles = []
        visual_rng = random.Random(73)
        for number in range(1, 46):
            z = visual_rng.uniform(-1, 1)
            angle = visual_rng.uniform(0, math.tau)
            distance = visual_rng.random() ** (1 / 3) * 0.80
            ring = math.sqrt(1 - z * z)
            position = (distance * ring * math.cos(angle), distance * ring * math.sin(angle), distance * z)
            velocity = tuple(visual_rng.uniform(-0.025, 0.025) for _ in range(3))
            self.particles.append({'position': position, 'velocity': velocity, 'sphere': Sphere(c, number)})
        self.flight = Sphere(c, 1)
        self.flight.hide()
        self._timer = None
        self.running = False
        self._flight = None
        self.last_number = None
        self.angle = 0.0
        self.set_count = 10
        self._render()
        self.bind('<Destroy>', self._destroyed)

    def _destroyed(self, event):
        if event.widget is self:
            self.stop()

    def _render(self):
        for index, line in enumerate(self.rings):
            points = []
            for step in range(49):
                t = step * math.tau / 48
                if index < 3:
                    latitude = (-0.5, 0, 0.5)[index]
                    radius = math.sqrt(1 - latitude * latitude)
                    point = (radius * math.cos(t), latitude, radius * math.sin(t))
                else:
                    meridian = (index - 3) * math.pi / 4
                    point = (math.cos(t) * math.cos(meridian), math.sin(t), math.cos(t) * math.sin(meridian))
                x, y, _ = project_point(*rotate_point(*point, self.angle))
                points.extend((x, y))
            self.canvas.coords(line, *points)
            self.canvas.tag_raise(line)
        projected = []
        for particle in self.particles:
            point = rotate_point(*particle['position'], self.angle)
            projected.append((point[2], point, particle['sphere']))
        # Far balls are painted first; near balls occlude them.
        for depth, point, sphere in sorted(projected, key=lambda item: item[0], reverse=True):
            x, y, perspective = project_point(*point)
            sphere.draw(x, y, 10 * perspective, light=0.83 - 0.16 * depth)
        for item in self.output.items:
            self.canvas.tag_raise(item)
        self.canvas.tag_raise(self.caption)

    def start(self):
        if not self.running:
            self.running = True
            self.canvas.itemconfigure(self.caption, text='MIXING IN 3D...')
            self._tick()

    def _tick(self):
        self._timer = None
        if not self.running:
            return
        self.angle += 0.018
        for particle in self.particles:
            particle['position'], particle['velocity'] = advance_particle(particle['position'], particle['velocity'])
        self._render()
        if self._flight is not None:
            number, step = self._flight
            progress = min(1.0, (step + 1) / 9)
            # Ball moves down the chute and toward the camera.
            z = 0.3 - 1.2 * progress
            x, y, perspective = project_point(0.13 * math.sin(progress * math.pi), progress * 1.03, z)
            self.flight.draw(x, y, (12 + progress * 7) * perspective, number=number)
            if progress == 1:
                self._flight = None
                self.flight.hide()
                self.output.draw(170, 302, 25, number=number)
            else:
                self._flight = number, step + 1
        self._timer = self.after(33, self._tick)

    def show_number(self, number, set_index, ball_index):
        self.last_number = number
        self.canvas.itemconfigure(self.caption, text=f'SET {set_index + 1}  /  BALL {ball_index + 1} OF 6')
        if self.running:
            self.output.hide()
            self._flight = number, 0
        else:
            self.output.draw(170, 302, 25, number=number)

    def stop(self):
        self.running = False
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        self._flight = None
        if self.canvas.winfo_exists():
            self.flight.hide()
            if self.last_number is not None:
                self.output.draw(170, 302, 25, number=self.last_number)

    def complete(self):
        self.stop()
        self.canvas.itemconfigure(self.caption, text=f'ALL {self.set_count} SETS COMPLETE')

    def reset(self):
        self.stop()
        self.last_number = None
        self.canvas.itemconfigure(self.caption, text='READY')
        self.canvas.itemconfigure(self.output.text, text='—')
