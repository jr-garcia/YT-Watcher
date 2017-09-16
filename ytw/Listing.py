import datetime
import webbrowser
from operator import itemgetter

from PySide.QtCore import QRect, QSize, Qt, Signal, Slot
from PySide.QtGui import *

from .Searching import SortingEnum
from ._paths import *

DEFAULT_DATE = '19800101'
MAX_DESCRIPTION_LEN = 400
THUMB_SIZE = 200


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

        lm.addLayout(lt)
        lm.addWidget(self.widgetData)

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
            rawDate = videoData['start_time']
            formatedStart = getDateObject(rawDate)

            rawDate = videoData['end_time'] or DEFAULT_DATE
            formatedEnd = getDateObject(rawDate)
            ld.addWidget(QLabel('Starts at: {} | Ends at {}'.format(str(formatedStart), str(formatedEnd), True)))
        else:
            rawDate = videoData['upload_date'] or DEFAULT_DATE
            formatedDate = getDateObject(rawDate)
            ld.addWidget(QLabel('{} | {:,} views'.format(str(formatedDate), videoData['view_count'], True)))

        labelUploader = QLabel()
        url = videoData['uploader_url']
        if url:
            labelUploader.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
            labelUploader.setOpenExternalLinks(True)
            uploaderStr = "<a href=\"{}\">{}</a>".format(url, videoData['uploader'])
        else:
            uploaderStr = videoData['uploader']

        labelUploader.setText(uploaderStr)
        ld.addWidget(labelUploader)
        desc = videoData['description']
        if len(desc) > MAX_DESCRIPTION_LEN:
            desc = desc[:MAX_DESCRIPTION_LEN] + '...'
        labelDesc = QLabel(desc)
        labelDesc.setWordWrap(True)

        labelDesc.setStyleSheet("QLabel {color : gray; }")
        labelDesc.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        ld.addWidget(labelDesc)

        ld.addStretch()

        self.setLayout(lm)

    @Slot(str, object)
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
        self.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.resize(self.sizeHint())

        like_count = likesReformat(videoData['like_count'])
        labelLike = QLabel(str(like_count), self)
        labelLike.setFixedWidth(THUMB_SIZE / 2)
        labelLike.setAlignment(Qt.AlignCenter)
        labelLike.setStyleSheet("QLabel { background-color : rgb(10, 155, 10); color : white; }")
        labelLike.move(0, THUMB_SIZE - labelLike.height())
        labelLike.show()

        dislike_count = likesReformat(videoData['dislike_count'])
        labelDislike = QLabel(str(dislike_count), self)
        labelDislike.setFixedWidth(THUMB_SIZE / 2)
        labelDislike.setAlignment(Qt.AlignCenter)
        labelDislike.setStyleSheet("QLabel { background-color : rgb(155, 10, 10); color : white; }")
        labelDislike.move(THUMB_SIZE / 2, THUMB_SIZE - labelDislike.height())
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
        labelDuration.setFixedWidth(THUMB_SIZE)
        labelDuration.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        labelDuration.move(0, THUMB_SIZE - labelDislike.height() - labelDuration.height())
        labelDuration.setStyleSheet("QLabel {color : white; font-size: 14px;}")
        labelDuration.show()

        is_live = videoData['is_live']
        if not is_live:
            labelDuration.setStyleSheet("QLabel {color : white; }")
            labelDuration.setText(str(datetime.timedelta(seconds=videoData['duration'])))
        else:
            labelDuration.setStyleSheet("QLabel {color : rgb(255, 30, 30); font-size: 14px;}")
            labelDuration.setText('LIVE')

        self.totalThumbHeight = THUMB_SIZE - (labelLike.height() * 2)
        self.visibleThumbHeight = THUMB_SIZE - (labelLike.height())

        if thumbPix is None:
            thumbPix = QPixmap(THUMB_SIZE, THUMB_SIZE)
            thumbPix.fill(QColor(0, 70, 100, 125))

        self.pixmap = None
        self.setThumbPixmap(thumbPix)

        title = videoData['title']

        if len(title) > 50:
            title = title[0:50] + '...'
        labelTitle = QLabel(title, self)
        labelTitle.setFixedWidth(THUMB_SIZE)
        labelTitle.setWordWrap(True)
        labelTitle.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        labelTitle.move(0, THUMB_SIZE - labelDislike.height() * 3)
        labelTitle.hide()
        self.labelTitle = labelTitle
        self.labelLike = labelLike
        self.labelDislike = labelDislike
        self.labelDuration = labelDuration

        desc = videoData['description']
        if len(desc) > MAX_DESCRIPTION_LEN * 2:
            desc = desc[:MAX_DESCRIPTION_LEN * 2] + '...'
        self.setToolTip(desc)

    def setThumbPixmap(self, newQpixmap):
        self.pixmap = newQpixmap.scaled(QSize(THUMB_SIZE, THUMB_SIZE), Qt.KeepAspectRatio, Qt.SmoothTransformation)

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
    sortingChanged = Signal()

    def __init__(self, iconAdd, iconTools, iconSearch):
        super(PreviewWidget, self).__init__(parent=None)

        self.iconDetail = QIcon(path.join(nuovolaPath, 'detailed.png'))
        self.iconIcon = QIcon(path.join(nuovolaPath, 'icon.png'))

        toolbarSearches = QToolBar()
        toolbarSearches.setObjectName('toolbarSearches')
        self.toolbarSearches = toolbarSearches
        ta = toolbarSearches.addAction(iconAdd, 'New search', self.queryNewSearch)
        ta.setShortcut('Ctrl+S')

        ta = toolbarSearches.addAction(iconTools, 'Configuration',
                                       lambda: QMessageBox.information(self, '', 'Not implemented'))
        ta.setShortcut('Ctrl+C')

        ta = toolbarSearches.addAction(iconSearch, 'Search properties')
        ta.setShortcut('Ctrl+P')
        ta.toggled.connect(self._searchPropertiesCheckChanged)
        ta.setCheckable(True)
        self.actionSearchProperties = ta

        menuViewModes = QMenu(self)

        g = QActionGroup(self, exclusive=True)
        g.triggered.connect(self.changeViewMode)

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

        comboSorting = QComboBox(toolbarSearches)
        comboSorting.addItems([getattr(SortingEnum, i) for i in dir(SortingEnum) if not i.startswith('_')])
        actionSorting = QWidgetAction(toolbarSearches)
        actionSorting.setDefaultWidget(comboSorting)
        toolbarSearches.addAction(actionSorting)
        self.actionSorting = actionSorting
        index = comboSorting.findText(SortingEnum.newest)
        comboSorting.setCurrentIndex(index)
        comboSorting.setEditable(False)
        comboSorting.currentIndexChanged.connect(self.sortItems)
        self.comboSorting = comboSorting

        tabWidget = QTabWidget()
        tabWidget.setObjectName('tabWidget')
        myTabBar = MyTabBar(tabWidget)
        tabWidget.setTabBar(myTabBar)
        self.tabWidget = tabWidget
        self.addEmptyTab()
        tabWidget.setMovable(True)
        tabWidget.setCornerWidget(toolbarSearches)
        tabWidget.currentChanged.connect(self._currentTabChanged)
        tabWidget.tabCloseRequested.connect(self._tabClosing)
        tabWidget.tabBar().tabMoved.connect(self.tabsMoved)

        layoutMain = QVBoxLayout()
        layoutMain.addWidget(self.tabWidget)

        layoutBottom = QHBoxLayout()
        buttonClear = QPushButton(QIcon(path.join(discoveryPath, 'clear.png')), 'Clear results')
        buttonClear.clicked.connect(self.clearList)
        buttonClear.setEnabled(False)
        self.buttonClear = buttonClear
        buttonForceSearchNow = QPushButton(QIcon(path.join(brightPath, 'search_find.png')), 'Search now')
        buttonForceSearchNow.clicked.connect(self.forceSearchNow)
        buttonForceSearchNow.setEnabled(False)
        self.buttonForceSearchNow = buttonForceSearchNow
        buttonMarkRead = QPushButton(QIcon(path.join(faiPath, 'Apply_modified.png')), 'Mark as read')
        buttonMarkRead.clicked.connect(self.markAsRead)
        buttonMarkRead.setEnabled(False)
        self.buttonMarkRead = buttonMarkRead
        layoutBottom.addWidget(buttonMarkRead)
        layoutBottom.addStretch()
        layoutBottom.addWidget(buttonForceSearchNow)
        layoutBottom.addStretch()
        layoutBottom.addWidget(buttonClear)

        layoutMain.addLayout(layoutBottom)

        self.setLayout(layoutMain)

        self._isEmpty = True
        self._isEmmitingCheckChanged = False
        self._onInitialPlacement = False
        self._isChangingVieModeFromButton = False
        self.isSetupSorting = False

    @Slot()
    def forceSearchNow(self):
        tabWidget = self.tabWidget
        listPreviews = tabWidget.widget(tabWidget.currentIndex())
        search = listPreviews.search
        search.forceSearchNow()

    @Slot()
    def sortItems(self):
        if self.isSetupSorting:
            return
        sortString = self.comboSorting.currentText()

        tabWidget = self.tabWidget
        currentIndex = tabWidget.currentIndex()
        listPreviews = tabWidget.widget(currentIndex)
        search = listPreviews.search
        search.sorting = sortString
        self._doActualSorting(listPreviews, search)

    def sortItemsFromSearch(self, search):
        if self.isSetupSorting:
            return

        tabWidget = self.tabWidget
        index = self.findTabIndexByWord(search.word)
        listPreviews = tabWidget.widget(index)
        self._doActualSorting(listPreviews, search)

    def setSortingModeFromSearch(self, search):
        sortString = search.sorting
        combo = self.comboSorting
        index = combo.findText(sortString)
        self.isSetupSorting = True
        combo.setCurrentIndex(index)
        self.isSetupSorting = False

    def _doActualSorting(self, listPreviews, search):
        results = search.currentResults
        sortString = search.sorting
        if len(results) == 1:
            return
        sortedResults = self._getSortedItemPlaces(results, sortString)
        form = self.parentWidget()
        listPreviews.clear()
        listPreviews.setUpdatesEnabled(False)
        for sortKey, videoId in sortedResults:
            videoInfo = results[videoId]
            self.appendVideoItem(search, videoInfo, form.retrieveThumbnail(videoInfo['id']))
            qApp.processEvents()

        listPreviews.setUpdatesEnabled(True)
        listPreviews.repaint()

    def _getSortedItemPlaces(self, results, sortString):
        sortedResults = []
        for key, val in results.items():
            if sortString in (SortingEnum.newest, SortingEnum.oldest):
                sortedResults.append((getDateObject(val['upload_date']), key))
            elif sortString == SortingEnum.views:
                sortedResults.append((val['view_count'], key))
            elif sortString == SortingEnum.likes:
                sortedResults.append((val['like_count'], key))
            elif sortString == SortingEnum.lenght:
                sortedResults.append((val['duration'], key))
        if sortString == SortingEnum.oldest:
            sortedResults.sort(key=itemgetter(0))
        else:
            sortedResults.sort(key=itemgetter(0), reverse=True)
        return sortedResults

    def markAsRead(self, listPreviews=None):
        if listPreviews is None:
            tabWidget = self.tabWidget
            listPreviews = tabWidget.widget(tabWidget.currentIndex())
        search = listPreviews.search
        search.isRead = True
        self.buttonMarkRead.setEnabled(False)

    def clearList(self):
        tabWidget = self.tabWidget
        listPreviews = tabWidget.widget(tabWidget.currentIndex())
        listPreviews.clear()
        search = listPreviews.search
        search.currentResults.clear()
        self.markAsRead(listPreviews)
        self.buttonClear.setEnabled(False)

    def clear(self):
        tabWidget = self.tabWidget
        while tabWidget.count() > 0:
            try:
                tabWidget.widget(0).clear()
            except Exception:
                pass
            tabWidget.removeTab(0)

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
        self._isEmpty = True
        tabWidget = self.tabWidget
        tabWidget.setTabsClosable(False)
        tabWidget.addTab(QWidget(), '[no searches]')
        self.setSearchRelatedToolsEnabled(False)

    def removeEmptyTab(self):
        self._isEmpty = False
        tabWidget = self.tabWidget
        tabWidget.removeTab(0)
        tabWidget.setTabsClosable(True)
        self.setSearchRelatedToolsEnabled(True)

    def setSearchRelatedToolsEnabled(self, state):
        self.actionViewModesMenu.setEnabled(state)
        self.actionSorting.setEnabled(state)
        try:
            self.buttonClear.setEnabled(state)
            self.buttonMarkRead.setEnabled(state)
            self.buttonForceSearchNow.setEnabled(state)
        except AttributeError:
            pass

    def queryNewSearch(self):
        suggested = 'cat' if self._isEmpty else ''
        word, ret = QInputDialog.getText(self, 'New search', 'Enter word to search for:', QLineEdit.Normal, suggested)
        if ret and word != '':
            self.newSearchRequested.emit(word)

    @Slot(int)
    def _currentTabChanged(self, index):
        word = self.tabWidget.tabText(index)
        if word != '':
            listPreviews = self.tabWidget.widget(index)
            try:
                search = listPreviews.search
            except AttributeError:
                return
            self.buttonMarkRead.setEnabled(not search.isRead)
            self.buttonClear.setEnabled(listPreviews.count())
            self.tabChanged.emit(word)
            self.setSortingModeFromSearch(search)

    def updateSearchesIndexes(self):
        for index in range(self.tabWidget.count()):
            word = self.tabWidget.tabText(index)
            self.searchIndexChanged.emit(word, index)

    def updateItemsViewMode(self, listWidget, viewMode):
        for i in range(listWidget.count()):
            item = listWidget.item(i)
            listWidget.itemWidget(item).setViewMode(viewMode)

    @Slot()
    def switchViewMode(self):
        listPreviews = self.tabWidget.widget(self.tabWidget.currentIndex())
        search = listPreviews.search
        self._isChangingVieModeFromButton = True
        viewMode = search.viewMode
        if viewMode == QListView.IconMode:
            self.actionListView.setChecked(True)
            viewMode = QListView.ListMode
            self.actionViewModesMenu.setIcon(self.iconDetail)
        else:
            self.actionIconView.setChecked(True)
            viewMode = QListView.IconMode
            self.actionViewModesMenu.setIcon(self.iconIcon)

        search.viewMode = viewMode
        self._isChangingVieModeFromButton = False
        listPreviews.setViewMode(viewMode)
        self.updateItemsViewMode(listPreviews, viewMode)

    def setViewModeFromSearch(self, search):
        listPreviews = self.tabWidget.widget(self.findTabIndexByWord(search.word))
        self._isChangingVieModeFromButton = True
        viewMode = search.viewMode
        if viewMode == QListView.ListMode:
            self.actionListView.setChecked(True)
            self.actionViewModesMenu.setIcon(self.iconDetail)
        else:
            self.actionIconView.setChecked(True)
            self.actionViewModesMenu.setIcon(self.iconIcon)

        self._isChangingVieModeFromButton = False
        listPreviews.setViewMode(viewMode)
        self.updateItemsViewMode(listPreviews, viewMode)

    @Slot()
    def changeViewMode(self):
        if self._isChangingVieModeFromButton:
            return
        listPreviews = self.tabWidget.widget(self.tabWidget.currentIndex())
        search = listPreviews.search
        if self.actionListView.isChecked():
            self.actionViewModesMenu.setIcon(self.iconDetail)
            search.viewMode = QListView.ListMode
        else:
            self.actionViewModesMenu.setIcon(self.iconIcon)
            search.viewMode = QListView.IconMode
        mode = search.viewMode
        listPreviews.setViewMode(mode)
        self.updateItemsViewMode(listPreviews, mode)

    @Slot(int)
    def _tabClosing(self, index):
        self.removeSearchRequested.emit(self.tabWidget.tabText(index))

    def addSearchTab(self, search, icon):
        if self._isEmpty:
            self.removeEmptyTab()

        listPreviews = QListWidget()
        listPreviews.search = search
        listPreviews.setResizeMode(QListView.Adjust)
        listPreviews.setMovement(QListView.Static)
        listPreviews.setObjectName(search.word)
        listPreviews.itemDoubleClicked.connect(self.openVideoInBrowser)
        tabWidget = self.tabWidget
        tabWidget.addTab(listPreviews, icon, search.word)
        search.index = tabWidget.count() - 1
        tabWidget.setCurrentIndex(search.index)
        self.setViewModeFromSearch(search)

    def removeSearchTab(self, search):
        index = search.index
        tabWidget = self.tabWidget
        tabWidget.removeTab(index)
        if tabWidget.count() == 0:
            self.addEmptyTab()
        else:
            self.updateSearchesIndexes()

    def appendVideoItem(self, search, data, thumbPix):
        sortString = search.sorting
        results = search.currentResults
        if len(results) == 1:
            place = -1
        else:
            place = 0
            videoID = data['id']
            sortedResults = self._getSortedItemPlaces(results, sortString)
            for i in range(len(sortedResults)):
                key, sortedVideoID = sortedResults[i]
                if videoID == sortedVideoID:
                    place = i
                    break

        return self.insertVideoItem(data, thumbPix, search.word, place)

    def insertVideoItem(self, data, thumbPix, word, place):
        index = self.findTabIndexByWord(word)
        if index is None:
            return
        if index == self.tabWidget.currentIndex():
            self.buttonMarkRead.setEnabled(True)
            self.buttonClear.setEnabled(True)
        listPreviews = self.tabWidget.widget(index)
        item = QListWidgetItem('')
        item.setSizeHint(QSize(200, 200))  # todo: make thumb size modifiable from mainUI
        newVideoItem = VideoItem(data, self, thumbPix)
        newVideoItem.setViewMode(listPreviews.search.viewMode)
        if place == -1:
            listPreviews.addItem(item)
        else:
            listPreviews.insertItem(place, item)
        listPreviews.setItemWidget(item, newVideoItem)
        return newVideoItem, item

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
        self.pixmap = QPixmap(path.join(iconPath, 'WAIS', 'Warning.png')).scaled(QSize(16, 16), Qt.KeepAspectRatio,
                                                                                 Qt.SmoothTransformation)
        super(MyTabBar, self).__init__(*args, **kwargs)

    def paintEvent(self, *args, **kwargs):
        super(MyTabBar, self).paintEvent(*args, **kwargs)

        painter = QPainter()
        painter.begin(self)

        selfRect = self.rect()
        tabWidget = self.parentWidget()

        for index in range(self.count()):
            listPreviews = tabWidget.widget(index)
            try:
                search = listPreviews.search
            except AttributeError:
                continue
            if search.isRead:
                continue
            oldrect = self.tabRect(index)
            point = selfRect.topLeft() + oldrect.center()
            point.setY(-1)
            painter.drawPixmap(point, self.pixmap)

        painter.end()


def getDateObject(rawDate):
    year, month, day = (int(i) for i in (rawDate[:4], rawDate[4:6], rawDate[6:]))
    return datetime.date(year, month, day)


def setApp(app):
    global qApp
    qApp = app
