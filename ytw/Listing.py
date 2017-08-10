from PySide.QtGui import *
from PySide.QtCore import Qt, Slot, QPoint, QRect, QSize
import datetime
import locale

# import webbrowser

MAXDESCRIPTIONLEN = 150
THUMBSIZE = 200


class VideoItem(QFrame):
    def __init__(self, videoData, parent, thumbPix):
        super(VideoItem, self).__init__(parent=parent)
        self.videoData = videoData
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        lm = QHBoxLayout()
        ld = QVBoxLayout()
        lt = QVBoxLayout()
        self.layoutMain = lm
        self.layoutData = ld
        self.layoutThumb = lt
        lm.addLayout(lt)
        lm.addLayout(ld)
        lm.addStretch()

        imageThumb = Thumbnail(videoData, thumbPix)
        self.thumb = imageThumb
        lt.addWidget(imageThumb)

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
            formatedStart = datetime.date(int(unformatedStart[:4]), int(unformatedStart[4:6]), int(unformatedStart[6:]))
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
        font = labelUploader.font()
        font.setUnderline(True)
        labelUploader.setFont(font)
        ld.addWidget(labelUploader)
        desc = videoData['description']
        if len(desc) > MAXDESCRIPTIONLEN:
            desc = desc[:MAXDESCRIPTIONLEN] + '...'
        labelDesc = QLabel(desc)
        labelDesc.setWordWrap(True)
        # labelDesc.resize(labelDesc.sizeHint())
        labelDesc.setMinimumWidth(100)
        labelDesc.setMinimumHeight(50)
        labelDesc.resize(2000, 100)
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

        # labelDurationShadow = QLabel(self)
        # labelDurationShadow.setFixedWidth(THUMBSIZE)
        # labelDurationShadow.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # labelDurationShadow.move(0, THUMBSIZE - labelDislike.height() - labelDurationShadow.height())
        # labelDurationShadow.show()
        # labelDurationShadow.setStyleSheet("QLabel {color : black; font-size: 14px;}")

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
            # labelDurationShadow.setText(str(datetime.timedelta(seconds=videoData['duration'])))
        else:
            labelDuration.setStyleSheet("QLabel {color : rgb(255, 30, 30); font-size: 14px;}")
            labelDuration.setText('LIVE')
            # labelDurationShadow.setText('LIVE')

        self.totalThumbHeight = THUMBSIZE - (labelLike.height() * 2)
        self.visibleThumbHeight = THUMBSIZE - (labelLike.height())

        if thumbPix is None:
            thumbPix = QPixmap(THUMBSIZE, THUMBSIZE)
            thumbPix.fill(QColor(0, 70, 100, 125))
        # imageThumb = QLabel(self)
        # imageThumb.setFixedSize(THUMBSIZE, THUMBSIZE)
        # imageThumb.move(0, 0)
        # self.imageThumb = imageThumb
        self.pixmap = None
        self.setThumbPixmap(thumbPix)
        # self.imageThumb.show()

    def setThumbPixmap(self, newQpixmap):
        self.pixmap = newQpixmap.scaled(QSize(THUMBSIZE, THUMBSIZE), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # self.imageThumb.setPixmap(
        #         newQpixmap.scaled(self.imageThumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

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