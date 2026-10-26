"""Windows GUI with Excel workbook input and output."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from model import BASE_RATE, estimate, recommend
from excel_io import read_draws, write_analysis, write_template


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('로또 6/45 · 베이지안 번호 추천')
        self.geometry('1020x800')
        self.minsize(850, 650)
        self.estimates = None
        self.draws = None
        self.ids = []
        self.numbers = []
        self.analysis_settings = None
        self.strength = tk.StringVar(value='412')
        self.uncertainty = tk.BooleanVar(value=False)
        self.result = tk.StringVar(value='412회 데이터를 입력해 주세요')
        self.status = tk.StringVar(value='회차를 포함하면 연속성과 중복도 검사합니다.')
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='최근 412회 엑셀 파일 분석', font=('', 15, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='.xlsx의 활성 시트 · 한 행에 회차 + 본번호 6개 또는 본번호 6개 · 보너스 제외').pack(anchor='w', pady=6)
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='엑셀 파일 열기 (.xlsx)', command=self.load).pack(side='left')
        ttk.Button(buttons, text='입력용 엑셀 양식 저장', command=self.template).pack(side='left', padx=6)
        text_frame = ttk.Frame(outer)
        text_frame.pack(fill='both', expand=True, pady=8)
        self.input = tk.Text(text_frame, height=10, wrap='none', state='disabled')
        scroll = ttk.Scrollbar(text_frame, command=self.input.yview)
        self.input.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.input.pack(fill='both', expand=True)
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        ttk.Label(controls, text='균등 사전 강도 (가상 회차 수)').pack(side='left')
        ttk.Entry(controls, textvariable=self.strength, width=9).pack(side='left', padx=6)
        ttk.Checkbutton(controls, text='사후 불확실성도 추출에 반영', variable=self.uncertainty).pack(side='left')
        ttk.Button(controls, text='분석 후 6개 추출', command=self.analyze).pack(side='right')
        ttk.Label(outer, textvariable=self.result, font=('', 23, 'bold'), foreground='#1455a0').pack(pady=12)
        ttk.Label(outer, textvariable=self.status, wraplength=950).pack(anchor='w')
        table_frame = ttk.Frame(outer)
        table_frame.pack(fill='both', expand=True, pady=8)
        self.table = ttk.Treeview(table_frame, columns=('n', 'count', 'mean', 'delta', 'sd'), show='headings', height=8)
        for key, title in zip(self.table['columns'], ['번호', '출현 횟수', '사후 포함확률 추정', '균등 대비 (%p)', '사후 표준편차 (%p)']):
            self.table.heading(key, text=title)
            self.table.column(key, width=160, anchor='center')
        table_scroll = ttk.Scrollbar(table_frame, command=self.table.yview)
        self.table.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side='right', fill='y')
        self.table.pack(fill='both', expand=True)
        ttk.Button(outer, text='추천 번호·분석 결과 엑셀 저장', command=self.save).pack(anchor='e')
        ttk.Label(outer, wraplength=950, text=(
            '모델: 번호별 Beta–Binomial 주변확률 추정 → 추정값을 가중치로 순차 비복원추출. '
            '번호 간 독립 사후근사이며 6개 동시선택의 정확한 결합 사후분포는 아닙니다. '
            '표의 확률은 추출 알고리즘의 최종 포함확률과 다릅니다. '
            '공정한 추첨에서는 모든 조합의 1등 확률이 1/8,145,060이며 당첨 우위를 보장하지 않습니다.'
        )).pack(anchor='w', pady=8)

    def load(self):
        path = filedialog.askopenfilename(filetypes=[('Excel 통합 문서', '*.xlsx')])
        if not path:
            return
        try:
            self.load_path(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror('엑셀 읽기 실패', str(exc))

    def load_path(self, path):
        self.draws = None
        self.ids = []
        self.estimates = None
        self.numbers = []
        self.table.delete(*self.table.get_children())
        self.result.set('412회 데이터를 입력해 주세요')
        self.status.set('엑셀 파일 검사 중')
        self.input.configure(state='normal')
        self.input.delete('1.0', 'end')
        try:
            draws, ids, sheet = read_draws(path)
            self.draws, self.ids = draws, ids
            rows = [([ids[i]] if ids else []) + list(row) for i, row in enumerate(draws)]
            self.input.insert('1.0', '\n'.join('   '.join(map(str, row)) for row in rows))
            self.result.set('엑셀 입력 완료 · 분석 버튼을 누르세요')
            self.status.set(f'{Path(path).name} | 시트: {sheet} | 412회 검증 완료')
        except (OSError, ValueError):
            self.status.set('엑셀 입력 실패 · 파일을 수정한 후 다시 열어 주세요')
            raise
        finally:
            self.input.configure(state='disabled')

    def template(self):
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='로또_412회_입력양식.xlsx',
                                          filetypes=[('Excel 통합 문서', '*.xlsx')])
        if path:
            try:
                write_template(path)
                messagebox.showinfo('양식 저장 완료', '첫 행 아래에 실제 412회 데이터를 입력한 후 엑셀 파일 열기를 눌러 주세요.')
            except OSError as exc:
                messagebox.showerror('저장 실패', str(exc))

    def analyze(self):
        self.estimates = None
        self.table.delete(*self.table.get_children())
        self.result.set('분석 중')
        try:
            if self.draws is None:
                raise ValueError('먼저 최근 412회가 담긴 엑셀(.xlsx) 파일을 열어 주세요.')
            draws, ids = self.draws, self.ids
            strength = float(self.strength.get())
            self.estimates = estimate(draws, strength)
            numbers = recommend(self.estimates, self.uncertainty.get())
            self.numbers = numbers
            self.analysis_settings = (strength, self.uncertainty.get())
        except ValueError as exc:
            self.result.set('입력 확인이 필요합니다')
            self.status.set('분석 실패: 입력과 사전 강도를 확인하세요.')
            messagebox.showerror('입력 오류', str(exc))
            return
        self.result.set('   '.join(f'{n:02d}' for n in numbers))
        target = f'{min(ids)}~{max(ids)}회 → {max(ids) + 1}회 추천' if ids else '다음 회차 추천 (회차·최신성 미확인)'
        self.status.set(f'{target} | 412회 분석 완료 | 균등 기준 {BASE_RATE:.4%} | 다시 누르면 새 조합을 추출합니다.')
        for e in self.estimates:
            self.table.insert('', 'end', values=(e.number, e.count, f'{e.mean:.3%}',
                                               f'{(e.mean - BASE_RATE) * 100:+.3f}', f'{e.sd * 100:.3f}'))

    def save(self):
        if self.estimates is None:
            messagebox.showinfo('분석 필요', '먼저 데이터를 분석하세요.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='로또_분석결과.xlsx',
                                          filetypes=[('Excel 통합 문서', '*.xlsx')])
        if path:
            try:
                write_analysis(path, self.estimates, self.numbers, self.ids, *self.analysis_settings)
            except OSError as exc:
                messagebox.showerror('저장 실패', str(exc))


if __name__ == '__main__':
    App().mainloop()
