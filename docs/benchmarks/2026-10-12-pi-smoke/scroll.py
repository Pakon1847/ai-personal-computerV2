import os, sys, tempfile
from pathlib import Path
os.environ["QT_QPA_PLATFORM"]="offscreen"; tmp=Path(tempfile.mkdtemp()); os.environ["XDG_DATA_HOME"]=str(tmp)
from PySide6.QtCore import QEventLoop, QObject, QTimer
from aipc.ui import app as uiapp
def settle(ms=300):
    l=QEventLoop(); QTimer.singleShot(ms,l.quit); l.exec()
app, engine, w = uiapp.build(uiapp.Options(screen="shell", software=True, settings_path=tmp/"ui.json"))
win=engine.rootObjects()[0]; win.resize(1280,800); settle()
page=[o for o in win.findChildren(QObject) if o.objectName()=="workspace"][0]
lst=[o for o in win.findChildren(QObject) if o.objectName()=="chatList"][0]
big = int(sys.argv[1]) if len(sys.argv)>1 else 14
items=[{"user":True,"text":"สรุปข้อความนี้: "+"การประชุมคณะกรรมการประจำเดือนตุลาคม มีวาระสำคัญหลายเรื่อง "*big*4}]
page.setProperty("items", items); settle()
for i in range(6):
    v=page.property("items"); v=v.toVariant() if hasattr(v,"toVariant") else v
    page.setProperty("items", v+[{"ai":True,"text":"คำตอบ "+str(i)+" "+"ข้อความ "*80,"note":"","done":True,"skill":""},{"user":True,"text":"ถามต่อ "+str(i)}]); settle(400)
    print(i, "contentY", round(lst.property("contentY")), "contentH", round(lst.property("contentHeight")), "h", round(lst.property("height")), "atEnd", lst.property("atYEnd"))
win.grabWindow().save(str(Path(sys.argv[2] if len(sys.argv)>2 else "scroll.png")))
