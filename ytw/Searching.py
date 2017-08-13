from PySide.QtGui import *
from PySide.QtCore import QTimer, QObject

from .ParallellSearcher import Searcher, SearchTypesEnum
from multiprocessing import Queue, cpu_count, Pipe
from queue import Empty, Full
from collections import OrderedDict


class SearchStatesEnum(object):
    paused = 'paused'
    searching = 'searching'
    readyToSearch = 'ready'
    error = 'error'


class Search(QObject):
    def __init__(self, videosCache, thumbsCache, baseCallback, thumbsCallback, word='', excludeds=None,
                 status=SearchStatesEnum.readyToSearch, ):
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
        self._seconds = 0
        self.baseCallback = baseCallback
        self.results = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.performSearch)
        # self.timerResults = QTimer(self)
        # self.timerResults.timeout.connect(self._resultsCallback)
        # self.timerResults.start(1)
        self._isFirstRun = True
        self.error = None
        self._externalPause = False

        self.resultsQueue = []

        # if status == SearchStatesEnum.readyToSearch:
        #     self.timer.start(1)
        #     self._isFirstRun = False

        self.pool = Pool(4)
        self.pool.start()

    def setTimer(self, seconds):
        self._seconds = seconds * 1000

    def __repr__(self):
        return '\'{}\' , {} exclusions, {}'.format(self.word, len(self.excludeds), self.status)

    def performSearch(self):
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

        if searchType == SearchTypesEnum.word:
            self.setReady()
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
            videoID = result['id']
            self.results.append(videoID)
            if videoID not in self.thumbsCache:
                thumbURL = result['thumbnail']
                self.pool.appendTask(((thumbURL, videoID), SearchTypesEnum.thumb), self.thumbsHandler)

            self.baseCallback(self.word, result)

    def thumbsHandler(self, result):
        self.thumbsCallback(result)

    def _setSearching(self):
        # print('Searching for:', self.word)
        self.timer.stop()
        self.status = SearchStatesEnum.searching

    def setReady(self):
        seconds = 1 if self._isFirstRun else self._seconds
        self._isFirstRun = False
        self.status = SearchStatesEnum.readyToSearch
        self.timer.start(seconds)

    def setPaused(self):
        self.timer.stop()
        self.status = SearchStatesEnum.paused

    def terminate(self):
        self.timer.stop()
        # self.timerResults.stop()
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

        mainlay = QVBoxLayout()
        self.setLayout(mainlay)
        self._canceled = False

        glay = QFormLayout()
        mainlay.addLayout(glay)

        self.searchWordEdit = QLineEdit()
        self.searchWordEdit.setEnabled(False)
        self.excludedEdit = QPlainTextEdit()
        glay.addRow(QLabel('Word'), self.searchWordEdit)
        glay.addRow(QLabel('Exclude terms\n(one per line)'), self.excludedEdit)

        layoutEvery = QHBoxLayout()
        self.spinboxRefreshTime = QSpinBox()
        self.spinboxRefreshTime.setValue(2)
        comboEveryUnit = QComboBox()
        comboEveryUnit.addItems(['Seconds', 'Minutes', 'Hours'])
        comboEveryUnit.setCurrentIndex(1)
        self.comboEveryUnit = comboEveryUnit

        layoutEvery.addWidget(self.spinboxRefreshTime)
        layoutEvery.addWidget(self.comboEveryUnit)
        glay.addRow(QLabel('Update every'), layoutEvery)

        self.radioStarted = QRadioButton('Running')  # todo: implement state change on radio change
        self.radioStarted.setChecked(True)
        self.radioPaused = QRadioButton('Paused')
        layoutStates = QVBoxLayout()
        layoutStates.addWidget(self.radioStarted)
        layoutStates.addWidget(self.radioPaused)
        groupState = QGroupBox('State')
        groupState.setLayout(layoutStates)

        glay.addRow(groupState)

    def getRefreshTime(self):
        amount = self.spinboxRefreshTime.value()
        lowTex = self.comboEveryUnit.currentText().lower()
        if lowTex == 'minutes':
            amount *= 60
        if lowTex == 'hours':
            amount *= 60 * 60

        return amount

    def refresh(self, search):
        self.setWindowTitle('Search properties')

        self.searchWordEdit.setText(search.word)

        self.radioStarted.setChecked(True if search.status == SearchStatesEnum.readyToSearch else False)
        self.excludedEdit.setPlainText('\n'.join(search.excludeds))
        self.searchWordEdit.setEnabled(False)
        super(SearchPropertiesWidget, self).show()

    def close(self, *args, **kwargs):
        self._canceled = True
        super(SearchPropertiesWidget, self).close()

    def ready(self):
        self.setResult(QDialog.Accepted)
        self.hide()


def setApp(app):
    global qApp
    qApp = app
