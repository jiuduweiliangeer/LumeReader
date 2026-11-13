"""Compact, persistent application navigation."""
from PyQt6.QtCore import Qt,QSize
from PyQt6.QtGui import QIcon,QPixmap
from PyQt6.QtWidgets import QFrame,QVBoxLayout
from .ui_parts import label,button
from .paths import APP_ROOT
from . import __version__


class Navigation(QFrame):
    def __init__(self,owner):
        super().__init__()
        self.owner=owner;self.setObjectName('Sidebar')
        self.box=QVBoxLayout(self);self.box.setSpacing(5)
        self.brand=label('lume.');self.brand.setStyleSheet('font-size:30px;font-weight:700;color:#2e6d50;')
        self.box.addWidget(self.brand)
        self.subtitle=label('电子书工具','Muted');self.box.addWidget(self.subtitle)
        self.box.addSpacing(26)
        self.titles=['书籍工作台','已完成','摘抄','设置与帮助']
        self.buttons=[]
        for i,(title,icon) in enumerate(zip(self.titles,('books','history','clippings','settings'))):
            b=button(title,lambda checked=False,index=i:owner.switch(index),'Nav')
            b.setCheckable(True);b.setIcon(QIcon(str(APP_ROOT/'lume/assets'/('nav-'+icon+'.svg'))))
            b.setIconSize(QSize(20,20));b.setMinimumHeight(44)
            b.setToolTip(title);b.setAccessibleName(title);self.box.addWidget(b);self.buttons.append(b)
        self.box.addStretch()
        self.footer=label('Lume Reader '+__version__,'Muted');self.box.addWidget(self.footer)
        self.toggle=button('',lambda:self.set_collapsed(not self.collapsed),'Quiet')
        self.toggle.setIconSize(QSize(20,20));self.toggle.setMinimumHeight(38);self.box.addWidget(self.toggle)
        self.set_collapsed(owner.config.get('sidebar_collapsed',True))

    def set_collapsed(self,value):
        self.collapsed=bool(value)
        self.owner.config['sidebar_collapsed']=self.collapsed
        self.setFixedWidth(60 if value else 152)
        self.box.setContentsMargins(8 if value else 10,20,8 if value else 10,14)
        self.subtitle.setVisible(not value);self.footer.setVisible(not value)
        self.brand.clear()
        if value:
            self.brand.setPixmap(QPixmap(str(APP_ROOT/'lume/assets/lume.png')).scaled(30,30,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.brand.setText('lume.');self.brand.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for b,title in zip(self.buttons,self.titles):
            b.setText('' if value else title)
            b.setStyleSheet('QPushButton#Nav {padding:10px;text-align:center;}' if value else
                             'QPushButton#Nav {padding:10px 8px;text-align:left;}')
        self.toggle.setText('' if value else '收起导航')
        self.toggle.setIcon(QIcon(str(APP_ROOT/'lume/assets'/('nav-expand.svg' if value else 'nav-collapse.svg'))))
        self.toggle.setToolTip('展开导航' if value else '收起导航')
        self.toggle.setAccessibleName(self.toggle.toolTip())