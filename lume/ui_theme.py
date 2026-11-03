"""An application-owned light palette, including menus and file dialogs."""
from PyQt6.QtGui import QColor,QPalette,QFont
from PyQt6.QtWidgets import QFileDialog as NativeFileDialog

def light_palette():
    palette=QPalette()
    colors={
        'Window':'#f5f7f8','WindowText':'#263b3b','Base':'#ffffff','AlternateBase':'#f5f8f6',
        'Text':'#263b3b','Button':'#ffffff','ButtonText':'#263b3b','BrightText':'#ffffff',
        'Highlight':'#dceee3','HighlightedText':'#244e39','ToolTipBase':'#f5faf7',
        'ToolTipText':'#263b3b','Link':'#28775f','LinkVisited':'#467b64',
        'Light':'#ffffff','Midlight':'#f0f5f2','Mid':'#c5d5cb','Dark':'#82988b','Shadow':'#596e61',
        'PlaceholderText':'#8b9890'}
    for name,value in colors.items():
        role=getattr(QPalette.ColorRole,name)
        for group in (QPalette.ColorGroup.Active,QPalette.ColorGroup.Inactive,QPalette.ColorGroup.Disabled):
            palette.setColor(group,role,QColor(value))
    for role in (QPalette.ColorRole.Text,QPalette.ColorRole.WindowText,QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled,role,QColor('#9aa9a0'))
    return palette

def apply_theme(app):
    from .ui_parts import STYLE
    app.setStyle('Fusion')
    app.setPalette(light_palette())
    app.setStyleSheet(STYLE)
    app.setFont(QFont('Microsoft YaHei UI',10))

class FileDialogs:
    """Use Qt dialogs so the file picker shares Lume's palette on dark Windows."""
    @staticmethod
    def _options(kwargs):
        kwargs['options']=kwargs.get('options',NativeFileDialog.Option(0))|NativeFileDialog.Option.DontUseNativeDialog
        return kwargs
    @staticmethod
    def getOpenFileNames(*args,**kwargs):
        return NativeFileDialog.getOpenFileNames(*args,**FileDialogs._options(kwargs))
    @staticmethod
    def getOpenFileName(*args,**kwargs):
        return NativeFileDialog.getOpenFileName(*args,**FileDialogs._options(kwargs))
    @staticmethod
    def getExistingDirectory(*args,**kwargs):
        return NativeFileDialog.getExistingDirectory(*args,**FileDialogs._options(kwargs))
