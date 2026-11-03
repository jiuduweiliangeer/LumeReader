"""Render the editable SVG as the Windows icon and README artwork."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import bootstrap
from PyQt6.QtCore import Qt,QRectF
from PyQt6.QtGui import QImage,QPainter
from PyQt6.QtSvg import QSvgRenderer
from PIL import Image
assets=root/'lume'/'assets'
renderer=QSvgRenderer(str(assets/'lume.svg'))
image=QImage(512,512,QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter=QPainter(image)
renderer.render(painter,QRectF(0,0,512,512))
painter.end()
image.save(str(assets/'lume.png'))
Image.open(assets/'lume.png').save(assets/'lume.ico',format='ICO',sizes=[(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(128,128),(256,256)])
print('Icon generated.')
