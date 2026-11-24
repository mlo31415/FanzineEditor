from __future__ import annotations

import wx


#==========================================================================================================
# Choose a fanzine index page's tags from the master list.
# Every tag in the master list is shown, in alphabetical order, with a checkbox; the page's tags are checked. A tag
# on the page which isn't in the master list (e.g. a typo in a hand-made page) is shown at the top in bold, unchecked:
# checking it keeps it on the page and adds it to the master list, just as New Tag would; leaving it unchecked drops it.
# After OK, CheckedTags is the page's new list of tags and NewMasterTags the tags to be added to the master list.
class EditTagsDialog(wx.Dialog):
    def __init__(self, parent: wx.Window|None, pageTags: list[str], masterTags: list[str]):
        wx.Dialog.__init__(self, parent, title="Edit Tags", style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)

        master={x.casefold() for x in masterTags}
        self._unlisted: list[str]=[]        # The page's tags which aren't in the master list
        for tag in pageTags:
            tag=tag.strip()
            if tag != "" and tag.casefold() not in master and tag.casefold() not in [x.casefold() for x in self._unlisted]:
                self._unlisted.append(tag)
        self._tags: list[str]=list(masterTags)      # The master list's tags, plus those added by New Tag
        self._new: list[str]=[]                     # The tags added by New Tag
        self._checked: set[str]={x.strip().casefold() for x in pageTags if x.strip().casefold() in master}     # (casefolded)
        self._boxes: dict[str, wx.CheckBox]={}      # Each tag's checkbox, by its casefolded name

        sizer=wx.BoxSizer(wx.VERTICAL)
        self._list=wx.ScrolledWindow(self, style=wx.VSCROLL)
        self._list.SetScrollRate(0, 10)
        sizer.Add(self._list, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 10)
        self.bNewTag=wx.Button(self, label="New Tag")
        self.bNewTag.Bind(wx.EVT_BUTTON, self.OnNewTag)
        sizer.Add(self.bNewTag, 0, wx.ALL, 10)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK|wx.CANCEL), 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 10)
        self.SetSizer(sizer)
        self.FillList()
        self.CenterOnParent()


    # (Re)create the checkboxes
    def FillList(self) -> None:
        self._list.DestroyChildren()
        self._boxes={}
        listSizer=wx.BoxSizer(wx.VERTICAL)
        for tag in self._unlisted+self._tags:
            cb=wx.CheckBox(self._list, label=tag.replace("&", "&&"))     # (A lone "&" would underline the next letter)
            if tag in self._unlisted:
                cb.SetFont(cb.GetFont().Bold())
            cb.SetValue(tag.casefold() in self._checked)
            cb.Bind(wx.EVT_CHECKBOX, lambda event, t=tag: self.OnCheck(t, event.IsChecked()))
            listSizer.Add(cb, 0, wx.ALL, 3)
            self._boxes[tag.casefold()]=cb
        if len(self._boxes) == 0:
            listSizer.Add(wx.StaticText(self._list, label="(The master list of tags is empty)"), 0, wx.ALL, 3)
        self._list.SetSizer(listSizer)
        # As tall as the list, up to a point: then it scrolls
        size=listSizer.GetMinSize()
        self._list.SetMinSize((max(250, size.width+wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)+10), min(400, size.height+5)))
        self._list.FitInside()
        self.Fit()


    def OnCheck(self, tag: str, checked: bool) -> None:
        if checked:
            self._checked.add(tag.casefold())
        else:
            self._checked.discard(tag.casefold())


    def OnNewTag(self, event):
        with wx.TextEntryDialog(self, "New tag:", "New Tag") as dlg:     # (with: destroyed on Cancel, too)
            if dlg.ShowModal() != wx.ID_OK:
                return
            tag=dlg.GetValue().strip()
        self.AddNewTag(tag)


    # Add a tag to the list, checked. A tag that's already listed (ignoring case) is just checked.
    def AddNewTag(self, tag: str) -> None:
        tag=tag.strip()
        if tag == "":
            return
        if "," in tag:
            wx.MessageBox(f"A tag can't contain a comma, so '{tag}' was not added.", "New Tag", wx.OK|wx.ICON_WARNING, parent=self)
            return
        self._checked.add(tag.casefold())
        if tag.casefold() in self._boxes:
            self._boxes[tag.casefold()].SetValue(True)
            return
        self._tags.append(tag)
        self._tags.sort(key=lambda x: x.casefold())
        self._new.append(tag)
        self.FillList()


    # The page's tags, in alphabetical order
    @property
    def CheckedTags(self) -> list[str]:
        return sorted([x for x in self._unlisted+self._tags if x.casefold() in self._checked], key=lambda x: x.casefold())

    # The tags to be added to the master list: those added by New Tag, and the page's unlisted tags which were checked
    @property
    def NewMasterTags(self) -> list[str]:
        return self._new+[x for x in self._unlisted if x.casefold() in self._checked]
