from __future__ import print_function

from json import dump, load
from multiprocessing import TimeoutError as PoolTimeOutError
from os import listdir, mkdir, remove

from .updateYT_DL import is_YTDL_importable, updateYTD

CACHEFILEEXT = '.cache'

WINDOWFILENAME = 'win.ini'

RESTARTREQUIRED = False

if not is_YTDL_importable():
    updateYTD(True)

from .Listing import *
from .Searching import *
from ._paths import *

# import urllib3 as ulib
from PySide.QtCore import QSettings, Signal


class MainWindow(QMainWindow):
    newThumbReady = Signal(str, object)

    def __init__(self):
        super(MainWindow, self).__init__()
        self.closedPerformed = False
        self.createFolderIfAbscent(CACHESPATH)
        self.createFolderIfAbscent(OPTIONSPATH)

        self.videoInfosCache = {}
        self.thumbsCache = {}
        self.thumbnailPixmaps = {}

        if not path.exists(CACHESPATH):
            mkdir(CACHESPATH)

        self.loadVideoInfosCache()
        self.loadThumbsCache()

        self.searchers = {}

        self.movieSearch = QMovie(path.join(iconPath, 'loading', 'loading.gif'))
        emptyPM = QPixmap(QSize(32, 32))
        emptyPM.fill(QColor(0, 0, 0, 0))
        self.iconSearching = QIcon(emptyPM)
        self.iconPaused = QIcon(path.join(brightPath, 'pause.png'))
        self.iconReady = QIcon(path.join(brightPath, 'clock.png'))
        self.iconSearch = QIcon(path.join(brightPath, 'edit.png'))
        self.iconAdd = QIcon(path.join(brightPath, 'plus_green.png'))
        self.iconTools = QIcon(path.join(brightPath, 'tools.png'))
        self.movieSearch.updated.connect(self.updateLoadingIcon)

        self._isChangedFromAction = False
        self.setWindowTitle('YT Watcher')
        self.setMinimumSize(QSize(700, 400))

        self.addWidgets()
        # self.statusBar().showMessage('Ready')
        self.resize(QSize(800, 600))
        self.setWindowIcon(QIcon(path.join(iconPath, 'logo.png')))
        self.center()
        self.searches = {}

        self.movieSearch.start()  # todo: start at first item addition

        # self.timerConection = QTimer()
        # self.timerConection.timeout.connect(self.checkConnection)
        # self.timerConection.start(5000)

        self.mainPool = Pool(6)
        self.mainPool.poolCrashed.connect(self.poolCrashed)
        self.mainPool.start()
        self.show()
        self.loadWindowsPlaces()
        self.loadSearches()
        # updateYTD()

        if len(self.searches.items()) == 0:
            self.previewsWidget.queryNewSearch()

    def searchPropertiesBoxCheckedChanged(self, isVisible):
        if self._isChangedFromAction:
            return
        self._isChangedFromAction = True
        if isVisible:
            self.dockSearchProperties.show()
        else:
            self.dockSearchProperties.hide()
        self._isChangedFromAction = False

    def searchPropertiesBoxVsibilityChanged(self):
        if self._isChangedFromAction:
            return
        self._isChangedFromAction = True
        self.previewsWidget.actionSearchProperties.setChecked(self.dockSearchProperties.isVisible())
        self._isChangedFromAction = False

    def updateLoadingIcon(self):
        pix = self.movieSearch.currentPixmap()
        self.iconSearching = QIcon(pix)
        for s in self.searches.values():
            searchStatus = s.status
            if s.isSearching():
                icon = self.iconSearching
            elif searchStatus == SearchStatesEnum.readyToSearch:
                icon = self.iconReady
            else:  # searchStatus == SearchStatesEnum.paused:
                icon = self.iconPaused
            self.previewsWidget.tabWidget.setTabIcon(s.index, icon)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def addWidgets(self):
        prevWid = PreviewWidget(self.iconAdd, self.iconTools, self.iconSearch)
        prevWid.newSearchRequested.connect(self.newSearchRequested)
        prevWid.removeSearchRequested.connect(self.removeSearchRequested)
        prevWid.tabChanged.connect(self.focusedSearchChanged)
        prevWid.searchPropertiesCheckChanged.connect(self.searchPropertiesBoxCheckedChanged)
        prevWid.searchIndexChanged.connect(self.searchIndexChanged)
        prevWid.setObjectName('previewsWidget')
        self.previewsWidget = prevWid

        self.setCentralWidget(prevWid)

        self.layoutMain = QHBoxLayout()
        self.setLayout(self.layoutMain)

        self.searchBox = SearchPropertiesWidget(self)
        self.searchBox.setRadioIcons(self.iconReady, self.iconPaused)
        self.searchBox.searchSortingChanged.connect(self.updateSorting)
        dockSearchProperties = QDockWidget()
        dockSearchProperties.setObjectName('dockSearchProperties')
        dockSearchProperties.visibilityChanged.connect(self.searchPropertiesBoxVsibilityChanged)
        dockSearchProperties.setEnabled(False)
        dockSearchProperties.setWidget(self.searchBox)
        dockSearchProperties.setWindowTitle('Search Properties')
        self.dockSearchProperties = dockSearchProperties
        self.addDockWidget(Qt.LeftDockWidgetArea, dockSearchProperties)

    def updateSorting(self):
        self.previewsWidget.clearList()

    def searchIndexChanged(self, word, index):
        self.searches[word].index = index

    def focusedSearchChanged(self, word):
        if word == '[no searches]':
            self.dockSearchProperties.setEnabled(False)
        else:
            self.dockSearchProperties.setEnabled(True)
            self.searchBox.refresh(self.searches[word])

    def newSearchRequested(self, word):
        if word in self.searches.keys():
            QMessageBox.critical(self, 'Wrong data', 'Word is already added to searches', QMessageBox.Ok)
            return

        self.createNewSearch(word)

    def removeSearchRequested(self, word):
        res = QMessageBox.question(self, 'Remove search',
                                   'Are you sure you want to remove search of \'{}\''.format(word), QMessageBox.Yes,
                                   QMessageBox.No)
        if res == QMessageBox.No:
            return
        fileName = '_' + word + CACHEFILEEXT
        filePath = path.join(searchesPath, fileName)
        if path.exists(filePath):
            remove(filePath)
        search = self.searches.pop(word)
        self.previewsWidget.removeSearchTab(search)
        search.terminate()

    def createNewSearch(self, word, isPaused=False):
        if isPaused:
            status = SearchStatesEnum.paused
        else:
            status = SearchStatesEnum.readyToSearch

        search = Search(self.videoInfosCache, self.thumbsCache, self.videoDataArrived, self.thumbReady, self.mainPool,
                        word, None, status)

        search.reStartRequired.connect(self.restartRequired)
        search.shutdownRequired.connect(self.searchCrashed)

        self.searches[word] = search

        if search.status == SearchStatesEnum.readyToSearch:
            icon = self.iconReady
            search.forceSearchNow()
        else:  # search.status == SearchStatesEnum.paused:
            icon = self.iconPaused

        self.previewsWidget.addSearchTab(search, icon)

        return search

    def videoDataArrived(self, word, result):
        videoID = result['id']
        if videoID not in self.videoInfosCache.keys():
            self.dumpVideoInfo(videoID, result)
            self.videoInfosCache[videoID] = result

        search = self.searches.get(word)
        if search is None:
            return

        thumbPix = self.retrieveThumbnail(videoID)

        res = self.previewsWidget.appendVideoItem(search, result, thumbPix)
        if res is None:
            return
        newVideoItem, item = res
        self.newThumbReady.connect(newVideoItem.thumbArrived)

    def retrieveThumbnail(self, videoID):
        if videoID in self.thumbsCache.keys():
            thumbPix = self.thumbnailPixmaps[videoID] = QPixmap(self.thumbsCache[videoID])
        else:
            thumbPix = None

        return thumbPix

    def thumbReady(self, result):
        videoID, thumbPath = result
        self.thumbsCache[videoID] = thumbPath
        self.newThumbReady.emit(videoID, self.retrieveThumbnail)

    def editSearchCallback(self, search):
        self.newSearchCallback(search, True)

    def searchCrashed(self, word, reason):
        self.raiseErrorToUI('Search error', 'Critical error while searching for \'{}\':\n{}\n'
                                            'Please report this issue.'.format(word, reason))

    def poolCrashed(self, reason):
        self.raiseErrorToUI('Pool error', 'Critical error in multiprocess pool:\n{}\n'
                                          'Please report this issue.'.format(reason))

    def raiseErrorToUI(self, title, msg):
        QMessageBox.critical(self, title, msg)
        self.close()

    def closeEvent(self, *args, **kwargs):
        if self.closedPerformed:
            return
        self.closedPerformed = True
        self.previewsWidget.clear()

        self.dumpSearches()
        self.saveWindowsPlaces()
        self.mainPool.terminate()

        for s in self.searches.values():
            s.terminate()

        super(MainWindow, self).closeEvent(*args, **kwargs)

    def saveWindowsPlaces(self):
        filePath = path.join(OPTIONSPATH, WINDOWFILENAME)
        if path.exists(filePath):
            remove(filePath)
        settings = QSettings(filePath, QSettings.IniFormat)
        # settings.setValue('dock.floating', int(self.dockSearchProperties.isFloating()))
        settings.setValue('geometry', self.saveGeometry())
        settings.setValue('state', self.saveState())

    def loadWindowsPlaces(self):
        filePath = path.join(OPTIONSPATH, WINDOWFILENAME)
        if not path.exists(filePath):
            return
        settings = QSettings(filePath, QSettings.IniFormat)

        self.restoreGeometry(settings.value('geometry'))
        self.restoreState(settings.value('state'))
        # self.dockSearchProperties.setFloating(bool(settings.value('dock.floating')))

    def dumpVideoInfo(self, videoID, info):
        if path.exists(cachedInfosPath):
            filenames = listdir(cachedInfosPath)

            fileName = '_' + videoID + CACHEFILEEXT
            if fileName not in filenames:
                filePath = path.join(cachedInfosPath, fileName)
                with open(filePath, 'x') as file:
                    dump(info, file, indent=4)

    def loadVideoInfosCache(self):
        self.createFolderIfAbscent(cachedInfosPath)

        for fileName in listdir(cachedInfosPath):
            fpath = path.join(cachedInfosPath, fileName)
            videoID, ext = path.splitext(fileName)
            videoID = videoID[1:]
            with open(fpath, 'r') as info:
                infoDict = load(info)
            self.videoInfosCache[videoID] = infoDict

    def dumpSearches(self):
        for word, s in self.searches.items():
            fileName = '_' + word + CACHEFILEEXT
            filePath = path.join(searchesPath, fileName)
            if path.exists(filePath):
                remove(filePath)
            with open(filePath, 'w') as file:
                searchInitDict = {'seconds': s.seconds, 'status': s.status, 'excludeds': s.excludeds, 'unit': s.unit,
                                  'index'  : s.index, 'searchMode': s.searchMode, 'max': s.maxResults,
                                  'viewMode': s.viewMode.name.decode(), 'sorting': s.sorting}
                dump(searchInitDict, file, indent=4)

    def loadSearches(self):
        self.createFolderIfAbscent(searchesPath)
        lastIndex = 0
        lastChecked = 0

        fileList = listdir(searchesPath)
        while len(fileList) > 0:
            fileName = fileList[lastChecked]
            fpath = path.join(searchesPath, fileName)
            word, ext = path.splitext(fileName)
            word = word[1:]
            with open(fpath) as info:
                searchInitDict = load(info)
                index = searchInitDict['index']
                if index > lastIndex:
                    lastChecked += 1
                    continue
                else:
                    fileList.pop(lastChecked)
                    lastIndex += 1
                    lastChecked = 0
                    status = searchInitDict['status']
                    if status == SearchStatesEnum.paused:
                        isPaused = True
                    else:
                        isPaused = False
                    search = self.createNewSearch(word, True)
                    search.seconds = searchInitDict['seconds']
                    search.excludeds = searchInitDict['excludeds']
                    search.unit = searchInitDict['unit']
                    search.maxResults = searchInitDict['max']
                    search.searchMode = searchInitDict['searchMode']
                    search.viewMode = QListView.ViewMode.values[searchInitDict['viewMode']]
                    search.sorting = searchInitDict['sorting']
                    self.previewsWidget.setViewModeFromSearch(search)
                    self.previewsWidget.setSortingModeFromSearch(search)
                    if not isPaused:
                        search.setReady()
                        search.forceSearchNow()
                    self.searchBox.refresh(search)

    def loadThumbsCache(self):
        self.createFolderIfAbscent(cachedThumbsPath)

        for fileName in listdir(cachedThumbsPath):
            videoID = fileName.split('_thumb')[0][1:]
            self.thumbsCache[videoID] = path.join(cachedThumbsPath, fileName)

    def createFolderIfAbscent(self, folderPath):
        if not path.exists(folderPath):
            mkdir(folderPath)

    def connectionCallback(self, res):
        if res:
            self.statusBar().showMessage('Connection Error!')
        else:
            self.statusBar().showMessage('Ready')

    def checkConnection(self):
        try:
            self.pool.map_async(_pickleableCheck, [''], callback=self.connectionCallback).get(1)
        except PoolTimeOutError:
            pass
        except Exception:
            raise

    def stopSearches(self):
        for s in self.searches:
            s._externalPause('pause')

    def restartRequired(self):
        global RESTARTREQUIRED
        RESTARTREQUIRED = True
        self.close()


def _pickleableCheck(dummy):
    con = ulib.connection_from_url('https://youtube.com')
    try:
        con.request('GET', '/', retries=None)
        return None
    except ulib.exceptions.HTTPError as err:
        return err
    except Exception:
        raise


class SearchPropertiesWidget(QWidget):
    searchSortingChanged = Signal()
    wordChanged = Signal(str)

    def __init__(self, parent):
        super(SearchPropertiesWidget, self).__init__(parent)

        self.search = None
        mainlay = QVBoxLayout()
        self.setLayout(mainlay)
        self._canceled = False

        layoutForm = QFormLayout()
        mainlay.addLayout(layoutForm)

        self.editWord = QLineEdit()
        self.editWord.setEnabled(False)
        self.editExcluded = QPlainTextEdit()
        self.editExcluded.textChanged.connect(self.excludedsChanged)

        layoutForm.addRow(QLabel('Word:'), self.editWord)
        layoutForm.addRow(QLabel('Exclude terms\n(one per line):'), self.editExcluded)

        layoutEvery = QHBoxLayout()
        self.spinboxRefreshTime = QSpinBox()
        self.spinboxRefreshTime.setValue(2)
        self.spinboxRefreshTime.setMinimum(1)
        comboEveryUnit = QComboBox()
        comboEveryUnit.addItems(['Seconds', 'Minutes', 'Hours'])
        comboEveryUnit.setCurrentIndex(1)
        comboEveryUnit.setEditable(False)
        self.comboEveryUnit = comboEveryUnit
        layoutEvery.addWidget(self.spinboxRefreshTime)
        layoutEvery.addWidget(self.comboEveryUnit)
        self.spinboxRefreshTime.valueChanged.connect(self.updateTimeChanged)
        self.comboEveryUnit.currentIndexChanged.connect(self.updateTimeChanged)
        layoutForm.addRow(QLabel('Update every:'), layoutEvery)

        self._internalReordering = True
        comboSearchMode = QComboBox()
        comboSearchMode.addItems(['Relevance', 'Date'])
        comboSearchMode.setCurrentIndex(1)
        comboSearchMode.setEditable(False)
        comboSearchMode.currentIndexChanged.connect(self.changedSorting)
        self.comboOrder = comboSearchMode
        layoutForm.addRow(QLabel('Mode:'), comboSearchMode)

        spinboxMaxResults = QSpinBox()
        spinboxMaxResults.setValue(50)
        spinboxMaxResults.setMinimum(1)
        spinboxMaxResults.valueChanged.connect(self.changedMaxResults)
        layoutForm.addRow(QLabel('Max results:'), spinboxMaxResults)
        self.spinboxMaxResults = spinboxMaxResults

        groupState = QGroupBox('State')
        self.radioStarted = QRadioButton('Running', groupState)  # todo: check state change on radio change
        self.radioStarted.setChecked(True)
        self.radioPaused = QRadioButton('Paused', groupState)
        self.radioPaused.toggled.connect(self.searchStatusChanged)
        layoutStates = QVBoxLayout()
        layoutStates.addWidget(self.radioStarted)
        layoutStates.addWidget(self.radioPaused)
        groupState.setLayout(layoutStates)

        layoutForm.addRow(groupState)
        self._onRefresh = False
        self._internalReordering = False

    def changedSorting(self):
        if self._internalReordering:
            return

        self.search.searchMode = self.comboOrder.currentIndex()
        self.searchSortingChanged.emit()
        if self.search.status != SearchStatesEnum.paused:
            self.search.forceSearchNow()

    def changedMaxResults(self, val):
        self.search.maxResults = val

    def getRefreshTime(self):
        amount = self.spinboxRefreshTime.value()
        lowTex = self.comboEveryUnit.currentText().lower()
        if lowTex == 'minutes':
            amount *= 60
        elif lowTex == 'hours':
            amount *= 60 * 60

        return amount

    def setRadioIcons(self, iconReady, iconPaused):
        self.radioStarted.setIcon(iconReady)
        self.radioPaused.setIcon(iconPaused)

    def refresh(self, search):
        word = search.word
        self.wordChanged.emit(word)
        self.editWord.setText(word)
        self._onRefresh = True
        self.search = search

        self.setWindowTitle(word.upper())

        if search.status == SearchStatesEnum.readyToSearch:
            self.radioStarted.setChecked(True)
        else:
            self.radioPaused.setChecked(True)

        self.editExcluded.setPlainText('\n'.join(search.excludeds))

        seconds = search.seconds
        index = 0

        if search.unit == 'minutes':
            index = 1
            seconds /= 60
        elif search.unit == 'hours':
            index = 2
            seconds /= 60
            seconds /= 60

        self.comboEveryUnit.setCurrentIndex(index)
        self.spinboxRefreshTime.setValue(seconds)

        self._internalReordering = True
        self.comboOrder.setCurrentIndex(search.searchMode)
        self.spinboxMaxResults.setValue(search.maxResults)
        self._internalReordering = False

        self._onRefresh = False

    def searchStatusChanged(self):
        if self._onRefresh:
            return
        if self.radioPaused.isChecked():
            self.search.setPaused()
        else:
            self.search.setReady()

    def excludedsChanged(self):
        text = self.editExcluded.toPlainText()
        if text != '':
            self.search.excludeds = text.split('\n')
        else:
            self.search.excludeds = []

    def updateTimeChanged(self):
        self.search.unit = self.comboEveryUnit.currentText().lower()
        if self.search.unit == 'seconds':
            minval = 10
        else:
            minval = 1
        self.spinboxRefreshTime.setMinimum(minval)
        self.search.seconds = self.getRefreshTime()

    def close(self, *args, **kwargs):
        self._canceled = True
        super(SearchPropertiesWidget, self).close()

    def ready(self):
        self.setResult(QDialog.Accepted)
        self.hide()


def runMainWindow():
    if not RESTARTREQUIRED:
        app = QApplication('')
    else:
        app = qApp
    setApp(app)
    mainWin = MainWindow()
    app.exec_()
    if RESTARTREQUIRED:
        runMainWindow()
