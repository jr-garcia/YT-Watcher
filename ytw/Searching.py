from PySide.QtGui import *
from PySide.QtCore import QTimer, QObject, Signal

from .ParallellSearcher import Searcher, SearchTypesEnum, DownloaderError
from multiprocessing import Queue, cpu_count, Pipe
from queue import Empty, Full
from collections import OrderedDict


class SearchStatesEnum(object):
    paused = 'paused'
    readyToSearch = 'ready'
    error = 'error'


class Search(QObject):
    notRead = Signal()

    def __init__(self, videosCache, thumbsCache, baseCallback, thumbsCallback, word='', excludeds=None,
                 status=SearchStatesEnum.readyToSearch):
        super(Search, self).__init__()
        self.thumbsCallback = thumbsCallback
        self.thumbsCache = thumbsCache
        self.videosCache = videosCache
        if excludeds is None:
            excludeds = []
        self.word = word
        self.excludeds = excludeds
        self.status = status
        self.index = -1
        self._miliseconds = 2 * 60 * 1000
        self.baseCallback = baseCallback
        self.results = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._performSearch)

        self._unit = 'minutes'
        self._lastFoundCount = 0

        self._isFirstRun = True
        self.error = None
        self._externalPause = False

        self.resultsQueue = []

        self.mode = QListView.ListMode

        self.pool = Pool(4)
        self.pool.start()
        self._isSearching = False
        self._isRead = True

    @property
    def isRead(self):
        return self._isRead

    @isRead.setter
    def isRead(self, value):
        self._isRead = value

    def isSearching(self):
        return self._isSearching

    @property
    def seconds(self):
        return int(self._miliseconds / 1000)

    @seconds.setter
    def seconds(self, value):
        self._miliseconds = value * 1000
        self.resetTimer()

    def __repr__(self):
        return '\'{}\' , {} exclusions, {}'.format(self.word, len(self.excludeds), self.status)

    def _performSearch(self):
        self._setSearching()
        self.pool.appendTask((self.word, SearchTypesEnum.word), self._resultsCallback)

    def _resultsCallback(self, returnValue):

        if not isinstance(returnValue, tuple):
            if issubclass(type(returnValue), YoutubeDLError):
                self.status = SearchStatesEnum.error
                self.error = returnValue
                return
            else:
                self.terminate()
                raise returnValue

        result, searchType = returnValue

        if isinstance(result, DownloaderError):
            print(result)  # todo:implement proper logging
            return

        if searchType == SearchTypesEnum.word:
            self._lastFoundCount = len(result['entries'])

            for video in result['entries']:
                videoID = video['id']
                if videoID in self.results:
                    continue
                if videoID not in self.videosCache.keys():
                    self.pool.appendTask((video['url'], SearchTypesEnum.video), self._resultsCallback)
                else:
                    cachedVideoResult = self.videosCache[videoID]
                    self._resultsCallback((cachedVideoResult, SearchTypesEnum.video))
        elif searchType == SearchTypesEnum.video:
            self._lastFoundCount -= 1
            if self._lastFoundCount == 0:
                self.setReady()
            videoID = result['id']
            self.results.append(videoID)
            if videoID not in self.thumbsCache.keys():
                thumbURL = result['thumbnail']
                self.pool.appendTask(((thumbURL, videoID), SearchTypesEnum.thumb), self.thumbsHandler)

            self.isRead = False
            self.baseCallback(self.word, result)

    def thumbsHandler(self, result):
        self.thumbsCallback(result)

    def _setSearching(self):
        self.timer.stop()
        self._isSearching = True

    def setReady(self):
        self._isSearching = False
        miliseconds = 1 if self._isFirstRun else self._miliseconds
        self._isFirstRun = False
        self.status = SearchStatesEnum.readyToSearch
        self.timer.start(miliseconds)

    def resetTimer(self):
        self.timer.stop()
        self.timer.start(self._miliseconds)

    def forceSearchNow(self):
        self._performSearch()

    def setPaused(self):
        self.timer.stop()
        self.status = SearchStatesEnum.paused

    def terminate(self):
        self.timer.stop()
        self.pool.terminate()

    def _externalPause(self, state):
        self.queue.put_nowait(state)


class Pool(QObject):
    def __init__(self, number=cpu_count(), *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)
        self._available = []
        self._busy = {}
        self.searchers = {}
        self.tasks = []
        self.remotes = {}
        self.locals = {}
        self.callbacks = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)

        for i in range(number):
            s = Searcher()
            sid = id(s)
            self.searchers[sid] = s
            client = Queue()
            client.cancel_join_thread()
            self.locals[sid] = client
            self.remotes[sid] = s.prepareConnections(client)
            s.start()
            self._available.append(sid)

    def start(self):
        self.timer.start(1)

    def stop(self):
        self.timer.stop()

    def appendTask(self, data, callback):
        self.tasks.append((data, callback))

    def update(self):
        while len(self._available) > 0:
            if len(self.tasks) == 0:
                break
            else:
                sid = self._available[0]
                try:
                    task, callback = self.tasks[0]
                    self.callbacks[sid] = callback
                    self._busy[sid] = sid
                    local = self.locals.get(sid)
                    local.put(task, timeout=1)
                    self._available.pop(0)
                    self.tasks.pop(0)
                except Full:
                    pass
                    # self._busy.pop(sid)
                    # self._available.append(sid)
                except AssertionError:
                    self.terminate()
                except OSError:
                    self.terminate()

        for ID, remote in self.remotes.items():
            qApp.processEvents()
            try:
                result = remote.get_nowait()
                self._busy.pop(ID)
                self._available.append(ID)
                self.callbacks[ID](result)
            except Empty:
                pass
            except OSError:
                self.terminate()
                return

    def terminate(self):
        for c in self.locals.values():
            try:
                c.put_nowait('')
                c.close()
            except OSError:
                pass
            except AssertionError:
                pass

        for s in self.searchers.values():
            s.terminate()


class SearchPropertiesWidget(QWidget):
    def __init__(self, parent):
        super(SearchPropertiesWidget, self).__init__(parent)

        self.search = None
        mainlay = QVBoxLayout()
        self.setLayout(mainlay)
        self._canceled = False

        glay = QFormLayout()
        mainlay.addLayout(glay)

        self.searchWordEdit = QLineEdit()
        self.searchWordEdit.setEnabled(False)
        self.excludedEdit = QPlainTextEdit()

        self.excludedEdit.textChanged.connect(self.excludedsChanged)
        glay.addRow(QLabel('Word'), self.searchWordEdit)
        glay.addRow(QLabel('Exclude terms\n(one per line)'), self.excludedEdit)

        layoutEvery = QHBoxLayout()
        self.spinboxRefreshTime = QSpinBox()
        self.spinboxRefreshTime.setValue(2)
        comboEveryUnit = QComboBox()
        comboEveryUnit.addItems(['Seconds', 'Minutes', 'Hours'])
        comboEveryUnit.setCurrentIndex(1)
        comboEveryUnit.setEditable(False)
        self.comboEveryUnit = comboEveryUnit

        layoutEvery.addWidget(self.spinboxRefreshTime)
        layoutEvery.addWidget(self.comboEveryUnit)
        self.spinboxRefreshTime.valueChanged.connect(self.updateTimeChanged)
        self.comboEveryUnit.currentIndexChanged.connect(self.updateTimeChanged)
        glay.addRow(QLabel('Update every'), layoutEvery)

        self.radioStarted = QRadioButton('Running')  # todo: implement state change on radio change
        self.radioStarted.setChecked(True)
        self.radioPaused = QRadioButton('Paused')
        self.radioPaused.toggled.connect(self.searchStatusChanged)
        layoutStates = QVBoxLayout()
        layoutStates.addWidget(self.radioStarted)
        layoutStates.addWidget(self.radioPaused)
        groupState = QGroupBox('State')
        groupState.setLayout(layoutStates)

        glay.addRow(groupState)
        self._onRefresh = False

    def getRefreshTime(self):
        amount = self.spinboxRefreshTime.value()
        lowTex = self.comboEveryUnit.currentText().lower()
        if lowTex == 'minutes':
            amount *= 60
        elif lowTex == 'hours':
            amount *= 60 * 60

        return amount

    def refresh(self, search):
        self._onRefresh = True
        self.search = search
        self.setWindowTitle('Search properties')

        self.searchWordEdit.setText(search.word)

        self.radioStarted.setChecked(True if search.status != SearchStatesEnum.paused else False)
        self.radioPaused.setChecked(not self.radioStarted.isChecked())
        self.excludedEdit.setPlainText('\n'.join(search.excludeds))
        self.searchWordEdit.setEnabled(False)

        seconds = search.seconds
        index = 0

        if search._unit == 'minutes':
            index = 1
            seconds /= 60
        elif search._unit == 'hours':
            index = 2
            seconds /= 60
            seconds /= 60

        self.comboEveryUnit.setCurrentIndex(index)
        self.spinboxRefreshTime.setValue(seconds)

        self._onRefresh = False

    def searchStatusChanged(self, event):
        if self._onRefresh:
            return
        if self.radioPaused.isChecked():
            self.search.setPaused()
        else:
            self.search.setReady()

    def excludedsChanged(self):
        text = self.excludedEdit.toPlainText()
        if text != '':
            self.search.excludeds = text.split('\n')
        else:
            self.search.excludeds = []

    def updateTimeChanged(self, event):
        self.search.seconds = self.getRefreshTime()
        self.search._unit = self.comboEveryUnit.currentText().lower()

    def close(self, *args, **kwargs):
        self._canceled = True
        super(SearchPropertiesWidget, self).close()

    def ready(self):
        self.setResult(QDialog.Accepted)
        self.hide()


def setApp(app):
    global qApp
    qApp = app
