"""Compact Windows GUI: Excel input and ten recommendations and a software-rendered 3D draw."""
from pathlib import Path
from datetime import timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from model import OUTPUT_COMPOSITION_PLAN as COMPOSITION_PLAN, SET_COUNT, estimate, balanced_recommendations, frequency_subgroups
from excel_io import read_workbook, write_recommendations, write_template
from draw_animation import LottoMachine, ball_color


class App(tk.Tk):
    WARMUP_MS = 900
    REVEAL_MS = 450
    SET_PAUSE_MS = 750

    def __init__(self):
        super().__init__()
        self.title('Lotto Generator')
        self.geometry('1220x980')
        self.minsize(1180, 940)
        self.revealing = False
        self.revealed_count = 0
        self._reveal_timer = None
        for name in tkfont.names(self):
            tkfont.nametofont(name, root=self).configure(family='Times New Roman')
        ttk.Style(self).configure('.', font=('Times New Roman', 11))
        self.data = None
        self.recommendations = []
        self.generated_strength = None
        self.prior_strength = 412.0
        self.filename = tk.StringVar(value='선택한 파일 없음')
        self.status = tk.StringVar(value='엑셀 파일을 선택해 주세요.')
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill='both', expand=True)
        self.header_image = tk.PhotoImage(file=str(Path(__file__).resolve().parent / 'assets' / 'lotto_header.png')).subsample(3)
        self.banner = tk.Canvas(outer, height=110, background='white', highlightthickness=0)
        self.banner.pack(fill='x', pady=(0, 10))
        image_id = self.banner.create_image(0, 55, image=self.header_image)
        self.banner.bind('<Configure>', lambda event: self.banner.coords(image_id, event.width / 2, 55))
        ttk.Label(outer, text='Lotto Generator', font=('Times New Roman', 19, 'bold')).pack(anchor='w', pady=(0, 12))
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        self.select_button = ttk.Button(controls, text='Select Input File', command=self.load)
        self.select_button.pack(side='left')
        ttk.Label(controls, textvariable=self.filename).pack(side='left', padx=10)
        self.generate_button = ttk.Button(controls, text='분석 후 10세트 추출', command=self.analyze)
        self.generate_button.pack(side='right')
        ttk.Label(outer, textvariable=self.status, wraplength=880).pack(anchor='w', pady=12)
        middle = ttk.Frame(outer)
        middle.pack(fill='x')
        middle.columnconfigure(0, weight=1, minsize=730)
        left = ttk.Frame(middle)
        left.grid(row=0, column=0, sticky='nw')
        self.machine = LottoMachine(middle)
        self.machine.grid(row=0, column=1, sticky='ne', padx=(12, 0))
        self.results_frame = ttk.Frame(left)
        self.results_frame.pack(fill='x')
        self.number_labels = []
        for index in range(SET_COUNT):
            row = ttk.Frame(self.results_frame, padding=(10, 2))
            row.pack(fill='x')
            ratio = ':'.join(map(str, COMPOSITION_PLAN[index]))
            ttk.Label(row, text=f'SET {index + 1}  ({ratio})', font=('Times New Roman', 12, 'bold'), width=18).pack(side='left')
            labels = []
            for _ in range(6):
                label = tk.Label(row, text='—', font=('Times New Roman', 17, 'bold'), width=3,
                                 background='#e9edf2', foreground='#6b7280', padx=8, pady=1)
                label.pack(side='left', padx=6)
                labels.append(label)
            self.number_labels.append(labels)
        self.group_frame = ttk.Frame(left, padding=(10, 4))
        self.group_frame.pack(fill='x', pady=(4, 0))
        ttk.Label(self.group_frame, text='가중치 순: 상위 5개 | 중위 5개 | 하위 5개 · 검정 굵게: 그룹 내 최고 가중치(동률 포함)',
                  font=('Times New Roman', 10), foreground='#687585').pack(anchor='w')
        self.group_vars = [tk.StringVar(value=f'{name}: —') for name in ('고빈도', '중빈도', '저빈도')]
        self.group_number_labels = []
        self.group_numbers = []
        self.group_weights = {}
        self.emphasized_numbers = set()
        for name in ('고빈도', '중빈도', '저빈도'):
            row = ttk.Frame(self.group_frame)
            row.pack(anchor='w', pady=1)
            ttk.Label(row, text=f'{name}: ', font=('Times New Roman', 10), foreground='#687585').pack(side='left')
            labels = []
            for index in range(15):
                if index in (5, 10):
                    ttk.Label(row, text=' | ', font=('Times New Roman', 10), foreground='#687585').pack(side='left')
                label = ttk.Label(row, text='—' if index == 0 else '', width=2,
                                  font=('Times New Roman', 10), foreground='#687585')
                label.pack(side='left', padx=2)
                labels.append(label)
            self.group_number_labels.append(labels)
        bottom = ttk.Frame(outer)
        bottom.pack(fill='x', pady=10)
        ttk.Button(bottom, text='입력용 엑셀 양식 저장', command=self.template).pack(side='left')
        self.save_button = ttk.Button(bottom, text='추천 10세트 엑셀 저장', command=self.save, state='disabled')
        self.save_button.pack(side='right')
        self.skip_button = ttk.Button(bottom, text='즉시 표시', command=self.finish_reveal, state='disabled')
        self.skip_button.pack(side='right', padx=8)
        ttk.Label(outer, text='동률은 무작위 선택 · 결과 유지 · 파일을 다시 선택하면 새로 추첨합니다.', wraplength=880).pack(anchor='w')
        ttk.Label(outer, text='모델 기준 상위 조합이며 실제 당첨 확률의 우위는 입증되지 않았습니다.',
                  wraplength=880, foreground='#6b7280').pack(anchor='w', pady=(4, 0))
        self.copyright_label = ttk.Label(outer, text='Hun-Kee, Lee All rights Reserved.',
                                         font=('Times New Roman', 10), foreground='#6b7280')
        self.copyright_label.pack(side='bottom', anchor='e', pady=(8, 0))
        self.bind('<Destroy>', self._on_destroy)

    def _on_destroy(self, event):
        if event.widget is self and self._reveal_timer is not None:
            self.after_cancel(self._reveal_timer)
            self._reveal_timer = None

    def cancel_reveal(self):
        if self._reveal_timer is not None:
            self.after_cancel(self._reveal_timer)
            self._reveal_timer = None
        self.revealing = False
        self.revealed_count = 0
        self.machine.reset()
        self.generate_button.configure(state='normal')
        self.skip_button.configure(state='disabled')
        self.save_button.configure(state='disabled')

    def clear_results(self):
        self.cancel_reveal()
        self.recommendations = []
        self.generated_strength = None
        for labels in self.number_labels:
            for label in labels:
                label.configure(text='—', background='#e9edf2', foreground='#6b7280')

    def load(self):
        path = filedialog.askopenfilename(filetypes=[('Excel 통합 문서', '*.xlsx')])
        if path:
            try:
                self.load_path(path)
            except (OSError, ValueError) as exc:
                messagebox.showerror('엑셀 읽기 실패', str(exc))

    def load_path(self, path):
        self.data = None
        self.clear_results()
        self.filename.set('선택한 파일 없음')
        for name, variable in zip(('고빈도', '중빈도', '저빈도'), self.group_vars):
            variable.set(f'{name}: —')
        self.group_numbers = []
        self.group_weights = {}
        self.emphasized_numbers = set()
        for row in self.group_number_labels:
            for index, label in enumerate(row):
                label.configure(text='—' if index == 0 else '', foreground='#687585', font=('Times New Roman', 10))
        try:
            self.data = read_workbook(path)
        except (OSError, ValueError):
            self.status.set('파일을 확인한 후 다시 선택해 주세요.')
            raise
        self.filename.set(Path(path).name)
        self.show_groups()
        interval = f' · {self.data.ids[0]}~{self.data.ids[-1]}회' if self.data.ids else ''
        self.status.set(f'전체 {len(self.data.draws)}회 입력 완료{interval}')

    def show_groups(self):
        estimates = estimate(self.data.draws, self.prior_strength)
        self.group_weights = {e.number: e.mean for e in estimates}
        subgroups = frequency_subgroups(estimates)
        self.group_numbers = [tuple(n for part in group for n in part) for group in subgroups]
        for name, variable, group in zip(('고빈도', '중빈도', '저빈도'), self.group_vars, subgroups):
            variable.set(f'{name}: ' + '  |  '.join(' '.join(f'{n:02d}' for n in part) for part in group))
        for numbers, row in zip(self.group_numbers, self.group_number_labels):
            for number, label in zip(numbers, row):
                label.configure(text=f'{number:02d}')
        highlighted = {number for numbers in self.group_numbers
                       for number in numbers if self.group_weights[number] == max(self.group_weights[n] for n in numbers)}
        self.render_group_emphasis(highlighted)

    def render_group_emphasis(self, highlighted):
        self.emphasized_numbers = set(highlighted)
        for numbers, row in zip(self.group_numbers, self.group_number_labels):
            for number, label in zip(numbers, row):
                emphasized = number in self.emphasized_numbers
                label.configure(foreground='#000000' if emphasized else '#687585',
                                font=('Times New Roman', 10, 'bold' if emphasized else 'normal'))

    def analyze(self):
        if self.revealing:
            return
        if self.recommendations and self.generated_strength == self.prior_strength:
            return
        self.clear_results()
        if self.data is None:
            messagebox.showinfo('입력 파일 필요', '먼저 Select Input File로 엑셀 파일을 선택해 주세요.')
            return
        try:
            self.recommendations = balanced_recommendations(estimate(self.data.draws, self.prior_strength))
            self.generated_strength = self.prior_strength
        except ValueError as exc:
            messagebox.showerror('분석 실패', str(exc))
            return
        self.revealing = True
        self.generate_button.configure(state='disabled')
        self.skip_button.configure(state='normal')
        self.machine.start()
        self.status.set('추첨 연출 중 · SET 1 준비')
        self._reveal_timer = self.after(self.WARMUP_MS, self.reveal_next)

    def reveal_next(self):
        self._reveal_timer = None
        if not self.revealing:
            return
        index = self.revealed_count
        set_index, ball_index = divmod(index, 6)
        number = self.recommendations[set_index].numbers[ball_index]
        label = self.number_labels[set_index][ball_index]
        label.configure(text=f'{number:02d}', background=ball_color(number), foreground='white')
        self.machine.show_number(number, set_index, ball_index)
        self.revealed_count += 1
        self.status.set(f'SET {set_index + 1} · 번호 {ball_index + 1}/6 공개 중 ({self.revealed_count}/{len(self.recommendations) * 6})')
        if self.revealed_count == len(self.recommendations) * 6:
            self._reveal_timer = self.after(self.REVEAL_MS, self.finish_reveal)
        else:
            delay = self.SET_PAUSE_MS if ball_index == 5 else self.REVEAL_MS
            self._reveal_timer = self.after(delay, self.reveal_next)

    def finish_reveal(self):
        if not self.revealing:
            return
        if self._reveal_timer is not None:
            self.after_cancel(self._reveal_timer)
            self._reveal_timer = None
        for result, labels in zip(self.recommendations, self.number_labels):
            for number, label in zip(result.numbers, labels):
                label.configure(text=f'{number:02d}', background=ball_color(number), foreground='white')
        self.revealed_count = len(self.recommendations) * 6
        self.revealing = False
        self.machine.show_number(self.recommendations[-1].numbers[-1], len(self.recommendations) - 1, 5)
        self.machine.complete()
        self.generate_button.configure(state='normal')
        self.skip_button.configure(state='disabled')
        self.save_button.configure(state='normal')
        target = f'{self.data.ids[-1] + 1}회 추천' if self.data.ids else '다음 회차 추천 (회차 미확인)'
        next_date = f' · {(self.data.dates[-1] + timedelta(days=7)).isoformat()} 예정' if self.data.dates else ''
        self.status.set(f'{target}{next_date} · 전체 {len(self.data.draws)}회 분석 완료')

    def template(self):
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='lotto_input_template.xlsx',
                                          filetypes=[('Excel 통합 문서', '*.xlsx')])
        if path:
            try:
                write_template(path)
            except OSError as exc:
                messagebox.showerror('저장 실패', str(exc))

    def save(self):
        if self.revealing:
            messagebox.showinfo('추첨 연출 중', '연출 완료를 기다리거나 즉시 표시를 눌러 주세요.')
            return
        if not self.recommendations:
            messagebox.showinfo('분석 필요', '먼저 분석 후 10세트 추출을 눌러 주세요.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='Lotto_Generator_10sets.xlsx',
                                          filetypes=[('Excel 통합 문서', '*.xlsx')])
        if path:
            try:
                write_recommendations(path, self.recommendations, self.data, self.prior_strength)
            except OSError as exc:
                messagebox.showerror('저장 실패', str(exc))


if __name__ == '__main__':
    App().mainloop()
