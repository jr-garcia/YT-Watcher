from PySide.QtGui import *
from PySide.QtCore import Qt, Slot, QPoint, QRect, QSize, Signal
import datetime
import locale
from os import path
import webbrowser

from ._paths import iconPath, nuovolaPath

MAXDESCRIPTIONLEN = 400
THUMBSIZE = 200


class VideoItem(QFrame):
    def __init__(self, videoData, parent, thumbPix):
        super(VideoItem, self).__init__(parent=parent)
        self.videoData = videoData
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        lm = QHBoxLayout()
        ld = QVBoxLayout()
        lt = QVBoxLayout()

        self.widgetData = QWidget()
        self.widgetData.setLayout(ld)
        # self.layoutMain = lm
        # self.layoutData = ld
        # self.layoutThumb = lt
        lm.addLayout(lt)
        lm.addWidget(self.widgetData)

        # lm.addStretch()

        imageThumb = Thumbnail(videoData, thumbPix)
        self.thumb = imageThumb
        lt.addWidget(imageThumb)

        self.viewMode = QListView.ListMode

        '''
        view_count
        subtitles
        chapters
        title
        series
        average_rating
        episode_number
        license
        categories
        is_live
        age_limit
        duration
        automatic_captions
        tags
        description
        formats
        start_time
        uploader_url
        thumbnail
        like_count
        annotations
        creator
        end_time
        upload_date
        season_number
        uploader_id
        uploader
        dislike_count
        id
        webpage_url
        alt_title
        '''

        labelTitle = QLabel(videoData['title'])
        labelTitle.setStyleSheet("QLabel {font-size: 16px;}")
        ld.addWidget(labelTitle)

        if videoData['start_time']:
            unformatedStart = videoData['start_time']
            formatedStart = datetime.date(int(unformatedStart[:4]), int(unformatedStart[4:6]), int(unformatedStart[
        6:]))
            unformatedEnd = videoData['end_time'] or '1980.1.1'
            formatedEnd = datetime.date(int(unformatedEnd[:4]), int(unformatedEnd[4:6]), int(unformatedEnd[6:]))
            ld.addWidget(QLabel('Starts at: {} | Ends at {}'.format(str(formatedStart), str(formatedEnd), True)))
        else:
            unformatedDate = videoData['upload_date']
            formatedDate = datetime.date(int(unformatedDate[:4]), int(unformatedDate[4:6]), int(unformatedDate[6:]))
            ld.addWidget(QLabel('{} | {:,} views'.format(str(formatedDate), videoData['view_count'], True)))

        labelUploader = QLabel()
        labelUploader.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        labelUploader.setOpenExternalLinks(True)
        labelUploader.setText("<a href=\"{}\">{}</a>".format(videoData['uploader_url'], videoData['uploader']))
        # font = labelUploader.font()
        # font.setUnderline(True)
        # labelUploader.setFont(font)
        ld.addWidget(labelUploader)
        desc = videoData['description']
        if len(desc) > MAXDESCRIPTIONLEN:
            desc = desc[:MAXDESCRIPTIONLEN] + '...'
        labelDesc = QLabel(desc)
        labelDesc.setWordWrap(True)
        # labelDesc.resize(labelDesc.sizeHint())
        # labelDesc.setMinimumWidth(100)
        # labelDesc.setMinimumHeight(50)
        # labelDesc.resize(2000, 100)
        labelDesc.setStyleSheet("QLabel {color : gray; }")
        labelDesc.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        ld.addWidget(labelDesc)

        ld.addStretch()

        self.setLayout(lm)

    @Slot()
    def thumbArrived(self, videoID, retrieverFuction):
        if videoID == self.videoData['id']:
            newQpixmap = retrieverFuction(videoID)
            self.thumb.setThumbPixmap(newQpixmap)

    def setViewMode(self, mode):
        if mode == QListView.IconMode:
            self.widgetData.hide()
            self.thumb.switchData(0)
        else:
            self.widgetData.show()
            self.thumb.switchData(1)

        self.viewMode = mode


def likesReformat(count):
    unit = ['', 'K', 'M']
    i = 0
    while count > 1000:
        count /= float(1000)
        i += 1
    finalCount = round(count, 1)
    if finalCount == int(finalCount):
        finalCount = int(finalCount)
    return '{} {}'.format(finalCount, unit[i])


class Thumbnail(QWidget):
    def __init__(self, videoData, thumbPix):
        super(Thumbnail, self).__init__()
        self.setFixedSize(THUMBSIZE, THUMBSIZE)
        self.resize(self.sizeHint())

        like_count = likesReformat(videoData['like_count'])
        labelLike = QLabel(str(like_count), self)
        labelLike.setFixedWidth(THUMBSIZE / 2)
        labelLike.setAlignment(Qt.AlignCenter)
        labelLike.setStyleSheet("QLabel { background-color : rgb(10, 155, 10); color : white; }")
        labelLike.move(0, THUMBSIZE - labelLike.height())
        labelLike.show()

        dislike_count = likesReformat(videoData['dislike_count'])
        labelDislike = QLabel(str(dislike_count), self)
        labelDislike.setFixedWidth(THUMBSIZE / 2)
        labelDislike.setAlignment(Qt.AlignCenter)
        labelDislike.setStyleSheet("QLabel { background-color : rgb(155, 10, 10); color : white; }")
        labelDislike.move(THUMBSIZE / 2, THUMBSIZE - labelDislike.height())
        labelDislike.show()

        if videoData['like_count'] > videoData['dislike_count']:
            font = labelLike.font()
            font.setBold(True)
            labelLike.setFont(font)
        else:
            font = labelDislike.font()
            font.setBold(True)
            labelDislike.setFont(font)

        labelDuration = QLabelS(self)
        labelDuration.setFixedWidth(THUMBSIZE)
        labelDuration.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        labelDuration.move(0, THUMBSIZE - labelDislike.height() - labelDuration.height())
        labelDuration.setStyleSheet("QLabel {color : white; font-size: 14px;}")
        labelDuration.show()

        is_live = videoData['is_live']
        if not is_live:
            labelDuration.setStyleSheet("QLabel {color : white; }")
            labelDuration.setText(str(datetime.timedelta(seconds=videoData['duration'])))
        else:
            labelDuration.setStyleSheet("QLabel {color : rgb(255, 30, 30); font-size: 14px;}")
            labelDuration.setText('LIVE')

        self.totalThumbHeight = THUMBSIZE - (labelLike.height() * 2)
        self.visibleThumbHeight = THUMBSIZE - (labelLike.height())

        if thumbPix is None:
            thumbPix = QPixmap(THUMBSIZE, THUMBSIZE)
            thumbPix.fill(QColor(0, 70, 100, 125))

        self.pixmap = None
        self.setThumbPixmap(thumbPix)

        title = videoData['title']

        if len(title) > 50:
            title = title[0:50] + '...'
        labelTitle = QLabel(title, self)
        labelTitle.setFixedWidth(THUMBSIZE)
        labelTitle.setWordWrap(True)
        labelTitle.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        labelTitle.move(0, THUMBSIZE - labelDislike.height() * 3)
        labelTitle.hide()
        self.labelTitle = labelTitle
        self.labelLike = labelLike
        self.labelDislike = labelDislike
        self.labelDuration = labelDuration

        desc = videoData['description']
        if len(desc) > MAXDESCRIPTIONLEN * 2:
            desc = desc[:MAXDESCRIPTIONLEN * 2] + '...'
        self.setToolTip(desc)

    def setThumbPixmap(self, newQpixmap):
        self.pixmap = newQpixmap.scaled(QSize(THUMBSIZE, THUMBSIZE), Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def switchData(self, state):
        if state == 0:
            self.labelDislike.hide()
            self.labelLike.hide()
            self.labelDuration.hide()
            self.labelTitle.show()
        else:
            self.labelDislike.show()
            self.labelLike.show()
            self.labelDuration.show()
            self.labelTitle.hide()

    def paintEvent(self, *args, **kwargs):
        painter = QPainter()
        painter.begin(self)

        devRect = QRect(painter.device().rect())
        devRect.setHeight(self.visibleThumbHeight)
        painter.fillRect(devRect, QColor(0, 0, 0))
        devRect.setHeight(self.totalThumbHeight)
        rect = QRect(self.pixmap.rect())
        rect.moveCenter(devRect.center())
        painter.drawPixmap(rect.topLeft(), self.pixmap)

        painter.end()


class QLabelS(QLabel):
    def __init__(self, parent):
        super(QLabelS, self).__init__(parent)

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)

        self.drawText(event, qp)
        qp.end()

    def drawText(self, event, qp):
        rct = event.rect()
        rct2 = QRect(event.rect())
        x = rct2.x()
        y = rct2.y()
        rct2.moveTo(x - 1, y - 1)
        qp.setPen(QColor(0, 0, 0))
        qp.drawText(rct, self.alignment(), self.text())

        qp.setPen(QColor(255, 255, 255))
        qp.drawText(rct2, self.alignment(), self.text())


class PreviewWidget(QWidget):
    newSearchRequested = Signal(str)
    removeSearchRequested = Signal(str)
    tabChanged = Signal(str)
    searchPropertiesCheckChanged = Signal(bool)
    searchIndexChanged = Signal(str, int)

    def __init__(self, iconAdd, iconTools, iconSearch):
        super(PreviewWidget, self).__init__(parent=None)

        self.iconDetail = QIcon(path.join(nuovolaPath, 'detailed.png'))
        self.iconIcon = QIcon(path.join(nuovolaPath, 'icon.png'))

        toolbarSearches = QToolBar()
        toolbarSearches.setObjectName('toolbarSearches')
        self.toolbarSearches = toolbarSearches
        ta = toolbarSearches.addAction(iconAdd, 'New search', self._queryNewSearch)
        ta.setShortcut('Ctrl+S')

        ta = toolbarSearches.addAction(iconTools, 'Configuration', lambda x: x)
        ta.setShortcut('Ctrl+C')

        ta = toolbarSearches.addAction(iconSearch, 'Search properties')
        ta.setShortcut('Ctrl+P')
        ta.toggled.connect(self._searchPropertiesCheckChanged)
        ta.setCheckable(True)
        self.actionSearchProperties = ta

        menuViewModes = QMenu(self)

        g = QActionGroup(self, exclusive=True)
        g.triggered.connect(self.changeViewMode)
        # self.groupViewMode = g

        actionListView = g.addAction(self.iconDetail, "List")
        actionListView.setCheckable(True)
        actionListView.setChecked(True)
        self.actionListView = actionListView

        actionIconView = g.addAction(self.iconIcon, "Icon")
        actionIconView.setCheckable(True)
        self.actionIconView = actionIconView

        menuViewModes.addAction(actionListView)
        menuViewModes.addAction(actionIconView)
        menuViewModes.setDefaultAction(actionListView)

        actionViewModesMenu = menuViewModes.menuAction()
        actionViewModesMenu.setIconVisibleInMenu(True)
        actionViewModesMenu.triggered.connect(self.switchViewMode)
        actionViewModesMenu.setToolTip('View mode')
        actionViewModesMenu.setIcon(self.iconDetail)
        self.actionViewModesMenu = actionViewModesMenu
        toolbarSearches.addAction(actionViewModesMenu)

        # actionViewModesMenu = toolbarSearches.addAction('View modes')
        # actionViewModesMenu.triggered.connect(self.switchViewMode)
        # actionViewModesMenu.setMenu(menuViewModes)

        tabWidget = QTabWidget()
        tabWidget.setObjectName('tabWidget')
        myTabBar = MyTabBar(tabWidget, )
        tabWidget.setTabBar(myTabBar)
        self.tabWidget = tabWidget
        self.addEmptyTab()
        tabWidget.setMovable(True)
        tabWidget.setCornerWidget(toolbarSearches)
        tabWidget.currentChanged.connect(self._currentChanged)
        tabWidget.tabCloseRequested.connect(self._tabClosing)
        tabWidget.tabBar().tabMoved.connect(self.tabsMoved)

        layoutMain = QVBoxLayout()
        layoutMain.addWidget(self.tabWidget)

        layoutBottom = QHBoxLayout()
        buttonClear = QPushButton('Clear results')
        buttonClear.clicked.connect(self.clearList)
        self.buttonClear = buttonClear
        buttonMarkRead = QPushButton('Mark as read')
        buttonMarkRead.clicked.connect(self.markAsRead)
        self.buttonMarkRead = buttonMarkRead
        layoutBottom.addWidget(buttonMarkRead)
        layoutBottom.addStretch()
        layoutBottom.addWidget(buttonClear)

        layoutMain.addLayout(layoutBottom)

        self.setLayout(layoutMain)

        self._isEmpty = True
        self._isEmmitingCheckChanged = False
        self._onInitialPlacement = False
        self._isChangingVieModeFromButton = False

    def markAsRead(self):
        listPreviews = self.tabWidget.widget(self.tabWidget.currentIndex())
        search = listPreviews.search
        search.isRead = True
        self.buttonMarkRead.setEnabled(False)

    def clearList(self):
        self.markAsRead()
        self.tabWidget.widget(self.tabWidget.currentIndex()).clear()
        self.buttonClear.setEnabled(False)

    def clear(self):
        while self.tabWidget.count() > 0:
            self.tabWidget.widget(0).clear()
            self.tabWidget.removeTab(0)

    def tabsMoved(self):
        if not self._onInitialPlacement:
            self.updateSearchesIndexes()

    def _searchPropertiesCheckChanged(self, event):
        if self._isEmmitingCheckChanged:
            return
        self._isEmmitingCheckChanged = True
        self.searchPropertiesCheckChanged.emit(event)
        self._isEmmitingCheckChanged = False

    def addEmptyTab(self):
        self._isEmpty = False
        self.tabWidget.setTabsClosable(False)
        self.tabWidget.addTab(QWidget(), '[no searches]')

    def removeEmptyTab(self):
        self._isEmpty = False
        self.tabWidget.removeTab(0)
        self.tabWidget.setTabsClosable(True)

    def _queryNewSearch(self):
        suggested = 'cat' if self._isEmpty else ''
        word, ret = QInputDialog.getText(self, 'New search', 'Enter word to search for:', QLineEdit.Normal, suggested)
        if ret and word != '':
            self.newSearchRequested.emit(word)

    def _currentChanged(self, index):
        word = self.tabWidget.tabText(index)
        if word != '':
            listPreviews = self.tabWidget.widget(index)
            search = listPreviews.search
            self.buttonMarkRead.setEnabled(not search.isRead)
            self.buttonClear.setEnabled(listPreviews.count())
            self.tabChanged.emit(word)

    def updateSearchesIndexes(self):
        for index in range(self.tabWidget.count()):
            word = self.tabWidget.tabText(index)
            self.searchIndexChanged.emit(word, index)

    def updateViewsViewMode(self, listWidget, viewMode):
        for i in range(listWidget.count()):
            item = listWidget.item(i)
            listWidget.itemWidget(item).setViewMode(viewMode)

    def switchViewMode(self):
        listPreviews = self.tabWidget.widget(self.tabWidget.currentIndex())
        search = listPreviews.search
        self._isChangingVieModeFromButton = True
        mode = search.mode
        if mode == QListView.IconMode:
            self.actionListView.setChecked(True)
            self.actionIconView.setChecked(False)
            search.mode = QListView.ListMode
            self.actionViewModesMenu.setIcon(self.iconDetail)
        else:
            self.actionListView.setChecked(False)
            self.actionIconView.setChecked(True)
            search.mode = QListView.IconMode
            self.actionViewModesMenu.setIcon(self.iconIcon)

        mode = search.mode
        self._isChangingVieModeFromButton = False
        listPreviews.setViewMode(mode)
        self.updateViewsViewMode(listPreviews,mode)

    def changeViewMode(self):
        if self._isChangingVieModeFromButton:
            return
        listPreviews = self.tabWidget.widget(self.tabWidget.currentIndex())
        search = listPreviews.search
        if self.actionListView.isChecked():
            self.actionViewModesMenu.setIcon(self.iconDetail)
            search.mode = QListView.ListMode
        else:
            self.actionViewModesMenu.setIcon(self.iconIcon)
            search.mode = QListView.IconMode
        mode = search.mode
        listPreviews.setViewMode(mode)
        self.updateViewsViewMode(listPreviews, mode)

    def _tabClosing(self, index):
        self.removeSearchRequested.emit(self.tabWidget.tabText(index))

    def add(self, search, icon):
        if self._isEmpty:
            self.removeEmptyTab()

        listPreviews = QListWidget()
        listPreviews.search = search
        listPreviews.setResizeMode(QListView.Adjust)
        listPreviews.setMovement(QListView.Static)
        listPreviews.setObjectName(search.word)
        listPreviews.itemDoubleClicked.connect(self.openVideoInBrowser)
        self.tabWidget.addTab(listPreviews, icon, search.word)
        search.index = self.tabWidget.count() - 1
        self.tabWidget.setCurrentIndex(search.index)

    def remove(self, search):
        index = search.index
        self.tabWidget.removeTab(index)
        if self.tabWidget.count() == 0:
            self.addEmptyTab()
        else:
            self.updateSearchesIndexes()

    def updateSearch(self, word, data, thumbPix):
        index = self.findTabIndexByWord(word)
        if index is None:
            raise IndexError(word)
        if index == self.tabWidget.currentIndex():
            self.buttonMarkRead.setEnabled(True)
            self.buttonClear.setEnabled(True)
        listPreviews = self.tabWidget.widget(index)
        item = QListWidgetItem('')
        item.setSizeHint(QSize(200, 200))

        newVideoItem = VideoItem(data, self, thumbPix)
        newVideoItem.setViewMode(listPreviews.search.mode)

        listPreviews.addItem(item)
        listPreviews.setItemWidget(item, newVideoItem)
        return newVideoItem

    def findTabIndexByWord(self, word):
        for index in range(self.tabWidget.count()):
            text = self.tabWidget.tabText(index)
            if text == word:
                return index

    def openVideoInBrowser(self, item):
        view = item.listWidget().itemWidget(item)
        webbrowser.open(view.videoData['webpage_url'])


class MyTabBar(QTabBar):
    def __init__(self, *args, **kwargs):
        self.pixmap = QPixmap(path.join(iconPath, 'WAIS', 'if_Warning_10596.png')).scaled(
            QSize(16, 16), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        super(MyTabBar, self).__init__(*args, **kwargs)

    def paintEvent(self, *args, **kwargs):
        super(MyTabBar, self).paintEvent(*args, **kwargs)

        painter = QPainter()
        painter.begin(self)

        selfRect = self.rect()
        tabWidget = self.parentWidget()

        for index in range(self.count()):
            listPreviews = tabWidget.widget(index)
            search = listPreviews.search
            if search.isRead:
                continue
            oldrect = self.tabRect(index)
            point = selfRect.topLeft() + oldrect.center()
            point.setY(-1)
            painter.drawPixmap(point, self.pixmap)

        painter.end()

