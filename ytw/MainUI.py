from __future__ import print_function

import sys
from json import dump, load
from multiprocessing import TimeoutError as PoolTimeOutError
from os import listdir, mkdir, remove

from .updateYT_DL import is_YTDL_importable, updateYTD

CACHEFILEEXT = '.cache'

WINDOWFILENAME = 'win.ini'

if not is_YTDL_importable():
    updateYTD(True)

from .Listing import *
from .Searching import *
from ._paths import *

import urllib3 as ulib
from PySide.QtCore import QSettings


class MainWindow(QMainWindow):
    newThumbReady = Signal(str, object)

    def __init__(self):
        super(MainWindow, self).__init__()
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
        self.iconSearch = QIcon(path.join(iconPath, 'search_tools.png'))
        self.iconAdd = QIcon(path.join(brightPath, 'plus_green.png'))
        self.iconTools = QIcon(path.join(brightPath, 'tools.png'))
        self.movieSearch.updated.connect(self.updateLoadingIcon)

        self._isChangedFromAction = False
        self.setWindowTitle('YT Watcher')
        self.setMinimumSize(QSize(700, 400))

        self._addWidgets()
        # self.statusBar().showMessage('Ready')
        self.resize(QSize(800, 600))
        self.setWindowIcon(QIcon(path.join(iconPath, 'logo.png')))
        self.center()
        self.searches = {}

        self.movieSearch.start()  # todo: start at first item addition

        # self.timerConection = QTimer()
        # self.timerConection.timeout.connect(self.checkConnection)
        # self.timerConection.start(5000)

        self.show()
        self.loadWindowsPlaces()
        self.loadSearches()
        # updateYTD()

        if len(self.searches.items()) == 0:
            self.previewsWidget._queryNewSearch()

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

    def _addWidgets(self):
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
        dockSearchProperties = QDockWidget()
        dockSearchProperties.setObjectName('dockSearchProperties')
        dockSearchProperties.visibilityChanged.connect(self.searchPropertiesBoxVsibilityChanged)
        dockSearchProperties.setEnabled(False)
        dockSearchProperties.setWidget(self.searchBox)
        # dockSearchProperties.resize(dockSearchProperties.size())
        # dockSearchProperties.resize(100, dockSearchProperties.size().height())
        dockSearchProperties.setWindowTitle('Search Properties')
        self.dockSearchProperties = dockSearchProperties
        self.addDockWidget(Qt.LeftDockWidgetArea, dockSearchProperties)

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
        res = QMessageBox.question(self, 'Remove search', 'Are you sure you want to remove search of \'{}\''.format(word),
                                   QMessageBox.Yes, QMessageBox.No)
        if res == QMessageBox.No:
            return
        search = self.searches.pop(word)
        self.previewsWidget.remove(search)

    def createNewSearch(self, word, fromInit=False):
        if fromInit:
            status = SearchStatesEnum.paused
        else:
            status = SearchStatesEnum.readyToSearch

        search = Search(self.videoInfosCache, self.thumbsCache, self.searchReady, self.thumbReady, word, None, status)

        search.callback = self.searchReady
        self.searches[word] = search

        if search.status == SearchStatesEnum.readyToSearch:
            icon = self.iconReady
            search.setReady()
        else:  # search.status == SearchStatesEnum.paused:
            icon = self.iconPaused

        self.previewsWidget.add(search, icon)

        return search

    def searchReady(self, word, result):
        videoID = result['id']
        if videoID not in self.videoInfosCache.keys():
            self.dumpVideoInfo(videoID, result)
            self.videoInfosCache[videoID] = result

        if videoID in self.thumbsCache.keys():
            thumbPix = self.retrieveThumbnail(videoID)
        else:
            thumbPix = None

        newVideoItem = self.previewsWidget.updateSearch(word, result, thumbPix)
        self.newThumbReady.connect(newVideoItem.thumbArrived)

    def retrieveThumbnail(self, videoID):
        if videoID not in self.thumbnailPixmaps.keys():
            self.thumbnailPixmaps[videoID] = QPixmap(self.thumbsCache[videoID])
        return self.thumbnailPixmaps[videoID]

    def thumbReady(self, result):
        data, searchType = result
        videoID, thumbPath = data
        self.thumbsCache[videoID] = thumbPath
        self.newThumbReady.emit(videoID, self.retrieveThumbnail)

    def editSearchCallback(self, search):
        self.newSearchCallback(search, True)

    def closeEvent(self, *args, **kwargs):
        self.previewsWidget.clear()

        self.dumpSearches()
        self.saveWindowsPlaces()

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
                searchInitDict = {'seconds': s.seconds, 'status': s.status, 'excludeds': s.excludeds, 'unit': s._unit,
                                  'index'  : s.index}
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
            with open(fpath, 'r') as info:
                searchInitDict = load(info)
                index = searchInitDict['index']
                if index > lastIndex:
                    lastChecked += 1
                    continue
                else:
                    fileList.pop(lastChecked)
                    lastIndex += 1
                    lastChecked = 0
                    search = self.createNewSearch(word, True)
                    search.seconds = searchInitDict['seconds']
                    status = searchInitDict['status']
                    search.excludeds = searchInitDict['excludeds']
                    search._unit = searchInitDict['unit']
                    if status == SearchStatesEnum.readyToSearch:
                        search.forceSearchNow()

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


def _pickleableCheck(dummy):
    con = ulib.connection_from_url('https://youtube.com')
    try:
        con.request('GET', '/', retries=None)
        return None
    except ulib.exceptions.HTTPError as err:
        return err
    except Exception:
        raise


def _runMainWindow():
    app = QApplication('')
    setApp(app)
    mainWin = MainWindow()
    sys.exit(app.exec_())
