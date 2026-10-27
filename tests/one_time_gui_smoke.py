import hashlib
from datetime import date
from pathlib import Path
import tempfile
from unittest.mock import patch
from openpyxl import load_workbook
from one_time_gui import OneTimeApp, PasswordWindow, SUBTITLE, main
from one_time_data import load_embedded_data
from one_time_access import LaunchLimiter
from model import passes_pattern_rules, SUBCOMPOSITION_PLAN


def texts(widget):
    found = []
    if 'text' in widget.keys():
        found.append(str(widget.cget('text')))
    for child in widget.winfo_children():
        found.extend(texts(child))
    return found


with tempfile.TemporaryDirectory() as temp, patch('one_time_access.PASSWORD_SHA256', hashlib.sha256(b'12345').hexdigest()), patch('one_time_access.current_local_date', return_value=date(2026, 10, 31)):
    limiter = LaunchLimiter(Path(temp) / 'usage.sqlite3')
    login = PasswordWindow(limiter)
    with patch('one_time_gui.messagebox.showerror') as error:
        login.password.set('00000')
        login.submit()
        assert error.call_count == 1 and limiter.used() == 0
    login.password.set('12345')
    login.submit()
    assert login.granted == 1 and limiter.used() == 1
    app = OneTimeApp(load_embedded_data(), 1)
    try:
        app.update()
        assert app.subtitle_label['text'] == SUBTITLE
        assert len(app.number_labels) == 5 and app.machine.set_count == 5
        assert 'Select Input File' not in texts(app)
        assert '입력용 엑셀 양식 저장' not in texts(app)
        try:
            app.load_path('anything.xlsx')
            raise AssertionError('external input must be disabled')
        except PermissionError:
            pass
        app.analyze()
        assert len(app.recommendations) == 5
        assert tuple(r.subcomposition for r in app.recommendations) == SUBCOMPOSITION_PLAN
        assert all(passes_pattern_rules(r.numbers) for r in app.recommendations)
        app.finish_reveal()
        assert app.revealed_count == 30
        assert 'ALL 5 SETS COMPLETE' == app.machine.canvas.itemcget(app.machine.caption, 'text')
        path = Path(temp) / 'results.xlsx'
        with patch('one_time_gui.filedialog.asksaveasfilename', return_value=str(path)):
            app.save()
        book = load_workbook(path)
        assert book['추천번호'].max_row == 6
        assert book['설정']['B2'].value == 1248
        assert ('추천 세트 수', 5) in list(book['설정'].values)
        book.close()
    finally:
        app.destroy()
    # Keep the password dialog open across midnight: do not consume a launch.
    expired_login = PasswordWindow(limiter)
    expired_login.password.set('12345')
    with patch('one_time_access.current_local_date', return_value=date(2026, 11, 1)), patch('one_time_gui.messagebox.showinfo') as info:
        expired_login.submit()
        assert info.call_args.args[1] == '실행할 수 있는 기한이 지났습니다.'
        assert expired_login.granted is None
    assert limiter.used() == 1
    # An already open app also expires and cancels animation/callbacks.
    expired_app = OneTimeApp(load_embedded_data(), 1)
    expired_app.analyze()
    with patch('one_time_access.current_local_date', return_value=date(2026, 11, 1)), patch('one_time_gui.messagebox.showinfo') as info:
        expired_app.analyze()
        assert info.call_args.args[1] == '실행할 수 있는 기한이 지났습니다.'
        assert expired_app._expiry_timer is None and expired_app._reveal_timer is None
        assert not expired_app.machine.running
    with patch('one_time_access.current_local_date', return_value=date(2026, 11, 1)), patch('one_time_gui.messagebox.showinfo') as info, patch('one_time_gui.load_embedded_data') as loader, patch('one_time_gui.PasswordWindow') as login_type:
        main()
        assert info.call_args.args[1] == '실행할 수 있는 기한이 지났습니다.'
        loader.assert_not_called()
        login_type.assert_not_called()
print('ONE_TIME_GUI_OK: wrong password uncharged, correct password, embedded data, no input UI, five sets, deadline boundary, expiry before password and across midnight, fixed export')
