'''
Created on Sep 14, 2012

@author: Mianwo
'''

import wx
from Checker import Checker, Plotter
import logging
import sys

class WxLog(logging.Handler):
    def __init__(self, ctrl):
        logging.Handler.__init__(self)
        self.ctrl = ctrl
    def emit(self, record):
        self.ctrl.AppendText(self.format(record)+"\n")

class Frame(wx.Frame):
    class RedirectText(object):
        def __init__(self,aWxTextCtrl):
            self.out=aWxTextCtrl
     
        def write(self,string):
            self.out.WriteText(string)
    
    def __init__(self, app, title):
        self.checker = Checker()
        self.plotter= Plotter()
        self.app = app
        
        wx.Frame.__init__(self, None, title=title, size=(400,400))
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        
        panel = wx.Panel(self)
        panel.SetBackgroundColour('#ededed')
        
        box = wx.BoxSizer(wx.VERTICAL)
        
        m_text = wx.StaticText(panel, -1, "Immigration Status Checker")
        m_text.SetFont(wx.Font(14, wx.SWISS, wx.NORMAL, wx.BOLD))
        m_text.SetSize(m_text.GetBestSize())
        box.Add(m_text, 0, wx.ALL, 10)
        
        id_box = wx.GridSizer(1, 2)
        m_id_text = wx.StaticText(panel, -1, "petition no.")
        id_box.Add(m_id_text, 0, wx.ALL, 10)
        
        self.m_id_textbox = wx.TextCtrl(panel)
        id_box.Add(self.m_id_textbox, 0, wx.ALL, 10)
        box.AddSizer(id_box)
        
        range_box = wx.GridSizer(1, 2)
        
        m_range_text = wx.StaticText(panel, -1, "range")
        m_range_text.SetSize(m_range_text.GetBestVirtualSize())
        range_box.Add(m_range_text, 0, wx.ALL, 10)
        
        self.m_range_textbox = wx.TextCtrl(panel, value="10")
        range_box.Add(self.m_range_textbox, 0, wx.ALL, 10)

        box.AddSizer(range_box)
        
        type_box = wx.BoxSizer(wx.HORIZONTAL)
        self.m_I140_checkbox = wx.CheckBox(panel, -1, 'I140')
        type_box.Add(self.m_I140_checkbox, 0, wx.ALL, 10)
        self.m_I485_checkbox = wx.CheckBox(panel, -1, 'I485')
        type_box.Add(self.m_I485_checkbox, 0, wx.ALL, 10)
        
        box.AddSizer(type_box)

        decision_box = wx.BoxSizer(wx.HORIZONTAL)
        self.m_submit = wx.Button(panel, wx.ID_APPLY, 'Submit')
        self.m_submit.Bind(wx.EVT_BUTTON, self.OnSubmit)
        decision_box.Add(self.m_submit, 0, wx.ALL, 20)

        m_close = wx.Button(panel, wx.ID_CLOSE, "Close")
        m_close.Bind(wx.EVT_BUTTON, self.OnClose)
        decision_box.Add(m_close, 0, wx.ALL, 20)
        
        self.m_clear = wx.Button(panel, wx.ID_CLEAR, 'Clear')
        self.m_clear.Bind(wx.EVT_BUTTON, self.OnClear)
        decision_box.Add(self.m_clear, 0, wx.ALL, 20)
        
        box.AddSizer(decision_box)
        
        self.m_report_to_file = wx.CheckBox(panel, -1, 'save to file?')
        box.Add(self.m_report_to_file, 0, wx.RIGHT | wx.ALIGN_RIGHT, 10)
                
        self.log = wx.TextCtrl(panel, wx.ID_ANY, size=(300,100), style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)
        box.Add(self.log, 0, wx.EXPAND|wx.ALL, 10)
        
        self.logr = logging.getLogger('')
        self.logr.setLevel(logging.INFO)
        hdlr = WxLog(self.log)
        hdlr.setFormatter(logging.Formatter('[%(levelname)s] %(asctime)-15s:  %(message)s'))
        self.logr.addHandler(hdlr)

        sys.stdout = Frame.RedirectText(self.log)
        sys.stderr = Frame.RedirectText(self.log)
        
        panel.SetSizer(box)
        panel.Layout()

    def OnClear(self, event):
        self.m_id_textbox.Clear()
        self.m_range_textbox.Clear()
        self.m_I140_checkbox.SetValue(False)
        self.m_I485_checkbox.SetValue(False)
        self.m_report_to_file.SetValue(False)
        self.log.Clear()

    def _validateFields(self):
        if not self.m_range_textbox.Value.isdigit() or int(self.m_range_textbox.Value) <= 0 or int(self.m_range_textbox.Value) > 100:
            dlg = wx.MessageDialog(self, "range needs to be an integer in (0, 100]", "Field Error", wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        elif not self.m_I140_checkbox.GetValue() and not self.m_I485_checkbox.GetValue():
            dlg = wx.MessageDialog(self, "needs to select at least from I140 and I485", "Field Error", wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        elif not self.checker.validateCase(self.m_id_textbox.GetValue()):
            dlg = wx.MessageDialog(self, "invalid status id", "Field Error", wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False
        else:
            return True

    def OnSubmit(self, event):
        try:
            self.m_submit.Disable()
            self.m_range_textbox.Disable()
            self.m_I140_checkbox.Disable()
            self.m_I485_checkbox.Disable()
            self.m_id_textbox.Disable()
            
            if not self._validateFields(): return
            else:
                t = []
                if self.m_I140_checkbox.GetValue(): t.append('I140')
                if self.m_I485_checkbox.GetValue(): t.append('I485')
                
                dialog = wx.ProgressDialog('progress bar', 'working...', int(self.m_range_textbox.GetValue()) * 2, self.m_range_textbox)
                stats = self.checker.taskManager(self.m_id_textbox.GetValue(), 
                                         int(self.m_range_textbox.GetValue()), 
                                         t, 
                                         self.logr,
                                         dialog,
                                         self.m_report_to_file.GetValue())
                self.plotter.plot(stats, t)
                dialog.Destroy()
        finally:
            wx.App.Yield(self.app)
            self.m_id_textbox.Enable()
            self.m_I485_checkbox.Enable()
            self.m_I140_checkbox.Enable()
            self.m_range_textbox.Enable()
            self.m_submit.Enable()

    def OnClose(self, event):
        self.Destroy()

app=wx.App(redirect=False)
top = Frame(app, "Immigration Status Checker")
top.Show()
app.MainLoop()
