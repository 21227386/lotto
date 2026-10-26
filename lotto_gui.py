"""Compact Windows GUI: Excel input and five reproducible recommendations."""
from pathlib import Path
from datetime import timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from model import COMPOSITION_PLAN, estimate, balanced_recommendations, frequency_subgroups
from excel_io import read_workbook, write_recommendations, write_template


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Lotto Generator')
        self.geometry('980x850')
        self.minsize(900, 820)
        for name in tkfont.names(self):
            tkfont.nametofont(name, root=self).configure(family='Times New Roman')
        ttk.Style(self).configure('.', font=('Times New Roman', 11))
        self.data = None
        self.recommendations = []
        self.prior_strength = 412.0
        self.filename = tk.StringVar(value='선택한 파일 없음')
        self.status = tk.StringVar(value='엑셀 파일을 선택해 주세요.')
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill='both', expand=True)
        self.header_image = tk.PhotoImage(file=str(Path(__file__).resolve().parent / 'assets' / 'lotto_header.png')).subsample(2)
        self.banner = tk.Canvas(outer, height=150, background='white', highlightthickness=0)
        self.banner.pack(fill='x', pady=(0, 10))
        image_id = self.banner.create_image(0, 75, image=self.header_image)
        self.banner.bind('<Configure>', lambda event: self.banner.coords(image_id, event.width / 2, 75))
        ttk.Label(outer, text='Lotto Generator', font=('Times New Roman', 19, 'bold')).pack(anchor='w', pady=(0, 12))
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        self.select_button = ttk.Button(controls, text='Select Input File', command=self.load)
        self.select_button.pack(side='left')
        ttk.Label(controls, textvariable=self.filename).pack(side='left', padx=10)
        ttk.Button(controls, text='분석 후 5세트 추출', command=self.analyze).pack(side='right')
        ttk.Label(outer, textvariable=self.status, wraplength=880).pack(anchor='w', pady=12)
        self.results_frame = ttk.Frame(outer)
        self.results_frame.pack(fill='x')
        self.number_labels = []
        for index in range(5):
            row = ttk.Frame(self.results_frame, padding=(10, 6))
            row.pack(fill='x')
            ratio = ':'.join(map(str, COMPOSITION_PLAN[index]))
            ttk.Label(row, text=f'SET {index + 1}  ({ratio})', font=('Times New Roman', 12, 'bold'), width=18).pack(side='left')
            labels = []
            for _ in range(6):
                label = tk.Label(row, text='—', font=('Times New Roman', 20, 'bold'), width=3,
                                 background='#e9edf2', foreground='#6b7280', padx=8, pady=3)
                label.pack(side='left', padx=6)
                labels.append(label)
            self.number_labels.append(labels)
        self.group_frame = ttk.Frame(outer, padding=(10, 4))
        self.group_frame.pack(fill='x', pady=(4, 0))
        ttk.Label(self.group_frame, text='가중치 순: 상위 5개 | 중위 5개 | 하위 5개',
                  font=('Times New Roman', 10), foreground='#687585').pack(anchor='w')
        self.group_vars = [tk.StringVar(value=f'{name}: —') for name in ('고빈도', '중빈도', '저빈도')]
        for variable in self.group_vars:
            ttk.Label(self.group_frame, textvariable=variable, font=('Times New Roman', 10),
                      foreground='#687585').pack(anchor='w', pady=1)
        bottom = ttk.Frame(outer)
        bottom.pack(fill='x', pady=10)
        ttk.Button(bottom, text='입력용 엑셀 양식 저장', command=self.template).pack(side='left')
        ttk.Button(bottom, text='추천 5세트 엑셀 저장', command=self.save).pack(side='right')
        ttk.Label(outer, text='구성: 고빈도 : 중빈도 : 저빈도 (각 15개 번호) · 동일 입력은 동일 결과', wraplength=880).pack(anchor='w')
        ttk.Label(outer, text='모델 기준 상위 조합이며 실제 당첨 확률의 우위는 입증되지 않았습니다.',
                  wraplength=880, foreground='#6b7280').pack(anchor='w', pady=(4, 0))
        self.copyright_label = ttk.Label(outer, text='Hun-Kee, Lee All rights Reserved.',
                                         font=('Times New Roman', 10), foreground='#6b7280')
        self.copyright_label.pack(side='bottom', anchor='e', pady=(8, 0))

    def clear_results(self):
        self.recommendations = []
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
        subgroups = frequency_subgroups(estimate(self.data.draws, self.prior_strength))
        for name, variable, group in zip(('고빈도', '중빈도', '저빈도'), self.group_vars, subgroups):
            variable.set(f'{name}: ' + '  |  '.join(' '.join(f'{n:02d}' for n in part) for part in group))

    def analyze(self):
        self.clear_results()
        if self.data is None:
            messagebox.showinfo('입력 파일 필요', '먼저 Select Input File로 엑셀 파일을 선택해 주세요.')
            return
        try:
            self.recommendations = balanced_recommendations(estimate(self.data.draws, self.prior_strength))
        except ValueError as exc:
            messagebox.showerror('분석 실패', str(exc))
            return
        for recommendation, labels in zip(self.recommendations, self.number_labels):
            for number, label in zip(recommendation.numbers, labels):
                color = '#e9b51f' if number <= 10 else '#2980c7' if number <= 20 else '#dc4d55' if number <= 30 else '#687585' if number <= 40 else '#39945c'
                label.configure(text=f'{number:02d}', background=color, foreground='white')
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
        if not self.recommendations:
            messagebox.showinfo('분석 필요', '먼저 분석 후 5세트 추출을 눌러 주세요.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='Lotto_Generator_5sets.xlsx',
                                          filetypes=[('Excel 통합 문서', '*.xlsx')])
        if path:
            try:
                write_recommendations(path, self.recommendations, self.data, self.prior_strength)
            except OSError as exc:
                messagebox.showerror('저장 실패', str(exc))


if __name__ == '__main__':
    App().mainloop()
