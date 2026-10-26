"""Real Tk integration check; requires a display. Uses synthetic data only."""
from pathlib import Path
import random
import tempfile
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
from excel_io import HEADERS
from lotto_gui import App


def run():
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / 'input.xlsx'
        output = Path(tmp) / 'output.xlsx'
        book = Workbook()
        book.active.append(HEADERS)
        rng = random.Random(43)
        for draw in range(836, 1248):
            book.active.append([draw] + rng.sample(range(1, 46), 6))
        book.save(source)
        book.close()
        app = App()
        errors = []
        try:
            app.update()
            with patch('lotto_gui.messagebox.showerror', side_effect=lambda *args: errors.append(args)):
                app.load_path(source)
                app.analyze()
                app.update()
                assert len(app.table.get_children()) == 45
                assert len(set(app.numbers)) == 6
                assert '1248' in app.status.get()
                with patch('lotto_gui.filedialog.asksaveasfilename', return_value=str(output)):
                    app.save()
                result = load_workbook(output)
                assert result['추천결과']['B2'].value == 1248
                result.close()
                app.uncertainty.set(True)
                app.analyze()
                assert len(set(app.numbers)) == 6
                app.strength.set('nan')
                app.analyze()
                assert app.estimates is None
                assert len(errors) == 1
                app.strength.set('412')
                app.analyze()
                try:
                    app.load_path(Path(tmp) / 'missing.xlsx')
                except ValueError:
                    pass
                assert app.draws is None and app.estimates is None
                assert len(app.table.get_children()) == 0
            print('GUI_SMOKE_OK: Excel load, 45 estimates, six unique numbers, Excel export, uncertainty, invalidation')
        finally:
            app.destroy()


if __name__ == '__main__':
    run()
