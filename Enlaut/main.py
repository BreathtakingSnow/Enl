import sys
import os
import json
import subprocess
import ctypes
import tempfile
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QFileDialog, QListWidget, QListWidgetItem, QMessageBox, QHBoxLayout,
    QSplitter, QFrame, QSizePolicy
)
from PyQt5.QtGui import QIcon, QPixmap, QFont, QCursor, QColor, QPainter, QTransform
from PyQt5.QtCore import Qt, QPoint, QSize, QTimer, QRectF


GAMES_FILE = 'games.json'
FAV_FILE = 'favorites.json'
ADD_ICON = '+'
BORDER_WIDTH = 6
TEMP_ICON_FOLDER = os.path.join(tempfile.gettempdir(), "enlaut_icons")
os.makedirs(TEMP_ICON_FOLDER, exist_ok=True)


class AnimatedBackground(QWidget):
    def __init__(self, parent=None, image_path=""):
        super().__init__(parent)
        self.angle = 0
        self.image_path = image_path
        self.pixmap = QPixmap(image_path)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_rotation)
        self.timer.start(30) 
        
    def update_rotation(self):
        self.angle = (self.angle - 1) % 360  # Вращение вправо
        self.update() 
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        visible_width = self.width() // 2
        full_width = self.width()
        x_offset = -(full_width - visible_width)
        
        transform = QTransform()
        transform.translate(self.width() // 2 + x_offset, self.height() // 2)
        transform.rotate(self.angle)
        transform.translate(-self.pixmap.width() // 2, -self.pixmap.height() // 2)
        
        painter.setTransform(transform)
        painter.drawPixmap(0, 0, self.pixmap)
        
    def resizeEvent(self, event):
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        super().resizeEvent(event)


class GameManager:
    @staticmethod
    def load_games():
        if os.path.exists(GAMES_FILE):
            with open(GAMES_FILE, 'r') as f:
                return json.load(f)
        return []

    @staticmethod
    def save_games(games):
        with open(GAMES_FILE, 'w') as f:
            json.dump(games, f, indent=4)

    @staticmethod
    def load_favorites():
        if os.path.exists(FAV_FILE):
            with open(FAV_FILE, 'r') as f:
                return json.load(f)
        return []

    @staticmethod
    def save_favorites(favs):
        with open(FAV_FILE, 'w') as f:
            json.dump(favs, f, indent=4)


class IconExtractor:
    @staticmethod
    def extract_icon(exe_path, ico_path):
        try:
            from PyQt5.QtWinExtras import QtWin
            large_icons = (ctypes.c_void_p * 1)()
            small_icons = (ctypes.c_void_p * 1)()
            n_icons = ctypes.windll.shell32.ExtractIconExW(exe_path, 0, large_icons, small_icons, 1)
            if n_icons > 0 and large_icons[0]:
                hicon = large_icons[0]
                pixmap = QtWin.fromHICON(hicon)
                if not pixmap.isNull():
                    pixmap.save(ico_path, "ICO")
                ctypes.windll.user32.DestroyIcon(hicon)
                return True
        except Exception as e:
            print(f"Ошибка извлечения иконки: {e}")
        return False


class FavoritesBar(QHBoxLayout):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(8)
        self.refresh_favorites()

    def refresh_favorites(self):
        while self.count() > 0:
            item = self.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for fav in GameManager.load_favorites():
            btn = QPushButton()
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(42, 42, 42, 220);
                    border: 1px solid #3a3a3a;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: rgba(58, 58, 58, 220);
                    border: 1px solid #4a4a4a;
                }
            """)
            if fav.get('icon') and os.path.exists(fav['icon']):
                pixmap = QPixmap(fav['icon'])
                if not pixmap.isNull():
                    btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(32, 32))
            btn.setFixedSize(40, 40)
            btn.setToolTip(fav['name'])
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda _, f=fav: self.show_fav_context_menu(f))
            btn.clicked.connect(lambda _, p=fav['path']: self.parent.launch_path(p))
            self.addWidget(btn)
        
        add_fav_btn = QPushButton(ADD_ICON)
        add_fav_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(42, 42, 42, 220);
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                color: white;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: rgba(58, 58, 58, 220);
                border: 1px solid #4a4a4a;
            }
        """)
        add_fav_btn.setFixedSize(32, 32)
        add_fav_btn.clicked.connect(self.add_to_favorites)
        self.addWidget(add_fav_btn)

    def show_fav_context_menu(self, fav):
        menu = QMessageBox(self.parent)
        menu.setWindowTitle("Избранное")
        menu.setText(f"Удалить '{fav['name']}' из избранного?")
        delete_btn = menu.addButton("Удалить", QMessageBox.DestructiveRole)
        cancel_btn = menu.addButton("Отмена", QMessageBox.RejectRole)
        menu.exec_()

        if menu.clickedButton() == delete_btn:
            favs = GameManager.load_favorites()
            favs = [f for f in favs if f['path'] != fav['path']]
            GameManager.save_favorites(favs)
            self.refresh_favorites()

    def add_to_favorites(self):
        current_item = self.parent.list_widget.currentItem()
        if current_item:
            path = current_item.data(Qt.UserRole)
            games = GameManager.load_games()
            favs = GameManager.load_favorites()
            
            for g in games:
                if g['path'] == path and not any(f['path'] == path for f in favs):
                    favs.append({
                        'name': g['name'], 
                        'path': g['path'], 
                        'icon': g.get('icon', '')
                    })
                    GameManager.save_favorites(favs)
                    self.refresh_favorites()
                    break


class GameList(QListWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setStyleSheet('''
            QListWidget {
                background-color: rgba(26, 26, 26, 220);
                color: #e0e0e0;
                font-size: 16px;
                border: none;
                border-radius: 8px;
            }
            QListWidget::item {
                height: 50px;
                border-bottom: 1px solid #2a2a2a;
                padding-left: 10px;
            }
            QListWidget::item:selected {
                background-color: rgba(42, 42, 42, 220);
                color: #ffffff;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: rgba(42, 42, 42, 220);
            }
        ''')
        self.setIconSize(QSize(32, 32))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_game_context_menu)
        self.itemClicked.connect(parent.display_game_details)
        self.itemDoubleClicked.connect(parent.launch_game)
        self.populate_games()

    def populate_games(self):
        self.clear()
        for game in GameManager.load_games():
            item = QListWidgetItem()
            item.setText(game['name'])
            if game.get('icon') and os.path.exists(game['icon']):
                pixmap = QPixmap(game['icon'])
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))
            item.setData(Qt.UserRole, game['path'])
            self.addItem(item)

    def show_game_context_menu(self, position):
        item = self.itemAt(position)
        if item:
            menu = QMessageBox(self.parent)
            menu.setWindowTitle("Выберите действие")
            menu.setText(f"Что сделать с '{item.text()}'?")
            fav_btn = menu.addButton("Добавить в избранное", QMessageBox.ActionRole)
            delete_btn = menu.addButton("Удалить игру", QMessageBox.DestructiveRole)
            cancel_btn = menu.addButton("Отмена", QMessageBox.RejectRole)
            menu.exec_()

            if menu.clickedButton() == fav_btn:
                self.setCurrentItem(item)
                self.parent.favorites_bar.add_to_favorites()
            elif menu.clickedButton() == delete_btn:
                game_path = item.data(Qt.UserRole)
                games = GameManager.load_games()
                games = [g for g in games if g['path'] != game_path]
                GameManager.save_games(games)
                self.populate_games()
                
                if self.parent.selected_game_path == game_path:
                    self.parent.game_details.clear_details()
                    self.parent.selected_game_path = None


class GameDetails(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setStyleSheet("""
            background-color: rgba(26, 26, 26, 220); 
            border-radius: 8px; 
            padding: 20px;
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        
        self.banner = QLabel()
        self.banner.setFixedHeight(200)
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setText("Баннер игры")
        self.banner.setStyleSheet("""
            background-color: rgba(18, 18, 18, 220); 
            color: #707070;
            border-radius: 8px;
            font-size: 18px;
        """)
        self.layout.addWidget(self.banner)

        details_header = QHBoxLayout()
        details_header.setContentsMargins(0, 0, 0, 0)
        details_header.setSpacing(20)
        
        icon_container = QWidget()
        icon_container.setFixedSize(80, 80)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)
        
        self.icon = QLabel()
        self.icon.setFixedSize(40, 40)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setStyleSheet("""
            background-color: transparent; 
            border: none;
        """)
        icon_layout.addWidget(self.icon)
        details_header.addWidget(icon_container)
        
        name_container = QVBoxLayout()
        self.name = QLabel("Выберите игру")
        self.name.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.name.setStyleSheet("color: #ffffff;")
        self.name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self.path_label = QLabel("")
        self.path_label.setFont(QFont("Segoe UI", 10))
        self.path_label.setStyleSheet("color: #a0a0a0;")
        self.path_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.path_label.setWordWrap(True)
        
        name_container.addWidget(self.name)
        name_container.addWidget(self.path_label)
        name_container.addStretch()
        details_header.addLayout(name_container, 1)
        self.layout.addLayout(details_header)

        button_container = QHBoxLayout()
        self.play_button = QPushButton("▶ Играть")
        self.play_button.setStyleSheet('''
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 16px;
                border-radius: 8px;
                padding: 12px 30px;
                border: none;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: rgba(26, 26, 26, 220);
                color: #606060;
            }
        ''')
        self.play_button.setFixedHeight(50)
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(parent.play_selected_game)
        button_container.addWidget(self.play_button, alignment=Qt.AlignCenter)
        self.layout.addLayout(button_container)

    def display_details(self, game):
        self.name.setText(game['name'])
        self.path_label.setText(game['path'])
        if game.get('icon') and os.path.exists(game['icon']):
            pixmap = QPixmap(game['icon'])
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.icon.width(), self.icon.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.icon.setPixmap(scaled_pixmap)
            else:
                self.icon.clear()
                self.icon.setText("")
        else:
            self.icon.clear()
            self.icon.setText("")
        self.play_button.setEnabled(True)

    def clear_details(self):
        self.name.setText("Выберите игру")
        self.path_label.setText("")
        self.icon.clear()
        self.icon.setText("")
        self.play_button.setEnabled(False)


class GameLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ENLAUT")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMouseTracking(True)
        self.resize(1280, 720)
        self.setAcceptDrops(True)
        self.oldPos = self.pos()
        self.dragging = False
        self.resizing = False
        self.resize_dir = None
        self.selected_game_path = None

        self.setStyleSheet("""
            QWidget {
                background-color: rgba(18, 18, 18, 150);
                color: #e0e0e0;
                font-family: 'Segoe UI';
            }
            QPushButton {
                background-color: rgba(42, 42, 42, 200);
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(58, 58, 58, 200);
            }
            QPushButton:pressed {
                background-color: rgba(26, 26, 26, 200);
            }
            QSplitter::handle {
                background-color: rgba(18, 18, 18, 150);
                width: 1px;
            }
        """)

        # Создаем анимированный фон
        background_image_path = "assets/1.png" 
        
        if os.path.exists(background_image_path):
            self.background = AnimatedBackground(self, background_image_path)
            self.background.setGeometry(0, 0, self.width(), self.height())
            self.background.lower()  # Отправляем фон на задний план
            self.background.setStyleSheet("background: transparent;")
        else:
            print(f"Background image not found: {background_image_path}")
            self.background = QWidget(self)
            self.background.setStyleSheet("background: black;")
            self.background.setGeometry(0, 0, self.width(), self.height())
            self.background.lower()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 0, 10, 0)
        top_bar.setSpacing(15)

        self.title_bar = QLabel("ENLAUT")
        self.title_bar.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.title_bar.setStyleSheet("color: #ffffff; background: transparent;")
        top_bar.addWidget(self.title_bar)

        top_bar.addStretch()

        self.favorites_bar = FavoritesBar(self)
        top_bar.addLayout(self.favorites_bar)
        top_bar.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(32, 32)
        settings_btn.setStyleSheet("font-size: 16px; background: rgba(42, 42, 42, 200);")
        settings_btn.setToolTip("Настройки")
        settings_btn.clicked.connect(self.show_settings)
        top_bar.addWidget(settings_btn)

        minimize_btn = QPushButton("–")
        minimize_btn.setFixedSize(32, 32)
        minimize_btn.setStyleSheet("font-size: 18px; background: rgba(42, 42, 42, 200);")
        minimize_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("font-size: 16px; background: rgba(42, 42, 42, 200);")
        close_btn.clicked.connect(self.close)

        top_bar.addWidget(minimize_btn)
        top_bar.addWidget(close_btn)

        main_layout.addLayout(top_bar)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(1) 
        content_splitter.setChildrenCollapsible(False)
        content_splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                background-color: rgba(42, 42, 42, 200);
                width: 1px;
            }
        """)

        left_container = QWidget()
        left_container.setStyleSheet("background: rgba(26, 26, 26, 200); border-radius: 8px;")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(15)
        
        list_label = QLabel("Мои игры")
        list_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #b0b0b0; background: transparent;")
        left_layout.addWidget(list_label)
        
        self.list_widget = GameList(self)
        left_layout.addWidget(self.list_widget)

        self.add_btn = QPushButton("➕ Добавить игру")
        self.add_btn.setStyleSheet("""
            padding: 12px;
            font-size: 16px;
            background-color: rgba(42, 42, 42, 200);
        """)
        self.add_btn.clicked.connect(self.add_game)
        left_layout.addWidget(self.add_btn)
        
        content_splitter.addWidget(left_container)

        right_container = QWidget()
        right_container.setStyleSheet("background: rgba(26, 26, 26, 200); border-radius: 8px;")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(15)
        
        details_label = QLabel("Детали игры")
        details_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #b0b0b0; background: transparent;")
        right_layout.addWidget(details_label)
        
        self.game_details = GameDetails(self)
        self.game_details.setStyleSheet("background: rgba(26, 26, 26, 200);")
        right_layout.addWidget(self.game_details)
        
        content_splitter.addWidget(right_container)

        content_splitter.setSizes([int(self.width() * 0.3), int(self.width() * 0.7)])
        
        main_layout.addWidget(content_splitter, 1)

    def resizeEvent(self, event):
        """Update background size when window is resized"""
        super().resizeEvent(event)
        if hasattr(self, 'background'):
            self.background.setGeometry(0, 0, self.width(), self.height())

    def show_settings(self):
        QMessageBox.information(self, "Настройки", "Раздел настроек будет добавлен в будущих обновлениях.")

    def add_game(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбери .exe игру", "", "EXE Files (*.exe)")
        if path:
            name = os.path.splitext(os.path.basename(path))[0]
            ico_path = os.path.join(TEMP_ICON_FOLDER, os.path.basename(path) + ".ico")

            if not IconExtractor.extract_icon(path, ico_path):
                ico_path = ''

            games = GameManager.load_games()
            games.append({
                'name': name, 
                'path': path, 
                'icon': ico_path
            })
            GameManager.save_games(games)
            self.list_widget.populate_games()

    def display_game_details(self, item):
        game_path = item.data(Qt.UserRole)
        for g in GameManager.load_games():
            if g['path'] == game_path:
                self.game_details.display_details(g)
                self.selected_game_path = g['path']
                break

    def play_selected_game(self):
        if self.selected_game_path:
            self.launch_path(self.selected_game_path)

    def launch_game(self, item):
        game_path = item.data(Qt.UserRole)
        self.launch_path(game_path)

    def launch_path(self, path):
        if not os.path.exists(path):
            QMessageBox.critical(self, "Ошибка", f"Файл не найден:\n{path}")
            return
        try:
            subprocess.Popen([path])
        except Exception as e:
            QMessageBox.critical(self, "Ошибка запуска", str(e))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = event.y() < 50
            self.oldPos = event.globalPos()
            self.resizing = self.resize_dir is not None
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False
        self.resize_dir = None
        self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()

        if self.resizing and self.resize_dir:
            delta = event.globalPos() - self.oldPos
            geom = self.geometry()

            if 'right' in self.resize_dir:
                geom.setWidth(geom.width() + delta.x())
            if 'bottom' in self.resize_dir:
                geom.setHeight(geom.height() + delta.y())
            if 'left' in self.resize_dir:
                geom.setLeft(geom.left() + delta.x())
            if 'top' in self.resize_dir:
                geom.setTop(geom.top() + delta.y())

            self.setGeometry(geom)
            self.oldPos = event.globalPos()
            return

        if self.dragging:
            delta = QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()
            return

        margin = BORDER_WIDTH
        self.resize_dir = ''
        if x < margin:
            self.resize_dir += 'left'
        elif x > w - margin:
            self.resize_dir += 'right'

        if y < margin:
            self.resize_dir += 'top'
        elif y > h - margin:
            self.resize_dir += 'bottom'

        cursors = {
            'left': Qt.SizeHorCursor,
            'right': Qt.SizeHorCursor,
            'top': Qt.SizeVerCursor,
            'bottom': Qt.SizeVerCursor,
            'lefttop': Qt.SizeFDiagCursor,
            'rightbottom': Qt.SizeFDiagCursor,
            'righttop': Qt.SizeBDiagCursor,
            'leftbottom': Qt.SizeBDiagCursor
        }
        self.setCursor(cursors.get(self.resize_dir, Qt.ArrowCursor))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = GameLauncher()
    launcher.show()
    sys.exit(app.exec_())