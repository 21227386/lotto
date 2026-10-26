"""Tk-only lottery-machine animation. Visual motion never selects real results."""
import math
import random
import tkinter as tk
from tkinter import ttk


def ball_color(number):
    return '#e9b51f' if number <= 10 else '#2980c7' if number <= 20 else '#dc4d55' if number <= 30 else '#687585' if number <= 40 else '#39945c'


class LottoMachine(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, width=340, height=365, bg='#101d35', highlightthickness=0)
        self.canvas.pack()
        c = self.canvas
        c.create_text(170, 23, text='LOTTO DRAW', fill='#f1f5fb', font=('Times New Roman', 17, 'bold'))
        c.create_oval(52, 42, 288, 278, fill='#172c47', outline='#3b7492', width=5)
        c.create_oval(61, 51, 279, 269, outline='#8ad4e6', width=2)
        c.create_arc(70, 60, 270, 260, start=40, extent=100, outline='#466c85', style='arc', width=6)
        c.create_polygon(152, 259, 188, 259, 193, 290, 147, 290, fill='#26415e', outline='#69b4cf', width=2)
        c.create_rectangle(91, 322, 249, 334, fill='#2e4560', outline='')
        self.caption = c.create_text(170, 350, text='READY', fill='#b6cbe0', font=('Times New Roman', 11))
        self.output_circle = c.create_oval(146, 282, 194, 330, fill='#26374f', outline='#6fa6c1', width=2)
        self.output_text = c.create_text(170, 306, text='—', fill='white', font=('Times New Roman', 22, 'bold'))
        self.particles = []
        visual_rng = random.Random(73)
        for i in range(22):
            angle = visual_rng.uniform(0, math.tau)
            radius = math.sqrt(visual_rng.random()) * 84
            x, y = 170 + radius * math.cos(angle), 160 + radius * math.sin(angle)
            number = (i * 7) % 45 + 1
            circle = c.create_oval(x - 11, y - 11, x + 11, y + 11, fill=ball_color(number), outline='#e0edf8', width=1)
            text = c.create_text(x, y, text=str(number), fill='white', font=('Times New Roman', 9, 'bold'))
            self.particles.append([x, y, visual_rng.uniform(-3, 3), visual_rng.uniform(-3, 3), circle, text])
        self.flight_circle = c.create_oval(0, 0, 0, 0, state='hidden')
        self.flight_text = c.create_text(0, 0, text='', state='hidden', font=('Times New Roman', 12, 'bold'), fill='white')
        self._timer = None
        self.running = False
        self._flight = None
        self.last_number = None
        self.bind('<Destroy>', self._destroyed)

    def _destroyed(self, event):
        if event.widget is self:
            self.stop()

    def start(self):
        if self.running:
            return
        self.running = True
        self.canvas.itemconfigure(self.caption, text='MIXING...')
        self._tick()

    def _tick(self):
        self._timer = None
        if not self.running:
            return
        for particle in self.particles:
            x, y, vx, vy, circle, text = particle
            dx, dy = x - 170, y - 160
            vx, vy = 0.997 * vx - 0.014 * dy, 0.997 * vy + 0.014 * dx
            speed = math.hypot(vx, vy)
            if speed > 5:
                vx, vy = vx * 5 / speed, vy * 5 / speed
            x, y = x + vx, y + vy
            dx, dy = x - 170, y - 160
            distance = math.hypot(dx, dy)
            if distance > 93:
                nx, ny = dx / distance, dy / distance
                projection = vx * nx + vy * ny
                vx, vy = vx - 2 * projection * nx, vy - 2 * projection * ny
                x, y = 170 + nx * 92, 160 + ny * 92
            particle[:4] = x, y, vx, vy
            self.canvas.coords(circle, x - 11, y - 11, x + 11, y + 11)
            self.canvas.coords(text, x, y)
        if self._flight is not None:
            number, step = self._flight
            progress = min(1, (step + 1) / 9)
            y = 165 + 141 * progress
            x = 170 + 18 * math.sin(progress * math.pi)
            radius = 12 + 12 * progress
            self.canvas.coords(self.flight_circle, x - radius, y - radius, x + radius, y + radius)
            self.canvas.coords(self.flight_text, x, y)
            if progress == 1:
                self._flight = None
                self.canvas.itemconfigure(self.flight_circle, state='hidden')
                self.canvas.itemconfigure(self.flight_text, state='hidden')
            else:
                self._flight = number, step + 1
        self._timer = self.after(33, self._tick)

    def show_number(self, number, set_index, ball_index):
        self.last_number = number
        self.canvas.itemconfigure(self.output_circle, fill=ball_color(number))
        self.canvas.itemconfigure(self.output_text, text=f'{number:02d}')
        self.canvas.itemconfigure(self.caption, text=f'SET {set_index + 1}  /  BALL {ball_index + 1} OF 6')
        if self.running:
            self._flight = number, 0
            self.canvas.itemconfigure(self.flight_circle, fill=ball_color(number), outline='white', state='normal')
            self.canvas.itemconfigure(self.flight_text, text=f'{number:02d}', state='normal')

    def stop(self):
        self.running = False
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        self._flight = None
        if self.canvas.winfo_exists():
            self.canvas.itemconfigure(self.flight_circle, state='hidden')
            self.canvas.itemconfigure(self.flight_text, state='hidden')

    def complete(self):
        self.stop()
        self.canvas.itemconfigure(self.caption, text='ALL 5 SETS COMPLETE')

    def reset(self):
        self.stop()
        self.last_number = None
        self.canvas.itemconfigure(self.caption, text='READY')
        self.canvas.itemconfigure(self.output_circle, fill='#26374f')
        self.canvas.itemconfigure(self.output_text, text='—')
