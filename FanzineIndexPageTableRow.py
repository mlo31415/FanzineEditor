from __future__ import annotations

from WxDataGrid import ColDefinitionsList, GridDataRowClass
from HelpersPackage import CanonicizeColumnHeaders

#=============================================================
# An individual fanzine to be listed in a fanzine index table
# This is a single row
class FanzineIndexPageTableRow(GridDataRowClass):

    def __init__(self, coldefs: ColDefinitionsList, row: None | list[str]=None):
        GridDataRowClass.__init__(self)
        self.FileSourcePath: str=""
        self._tableColdefs=coldefs
        self._Signature: int=0
        self._UpdatedComment: str=""
        if row is None:
            self._cells=[""]*len(self._tableColdefs)
        else:
            self._cells=row

        if self._cells[0] == "" and len(self._cells[1]) > 0:
            self._isText: bool=True
            self._cells[0]=self._cells[1]   # In a text row, the text now is stored in cell 0
            self._cells[1]=""
        else:
            self._isText: bool=False        # Is this a piece of text rather than a convention?

        self._isLink: bool=False        # Is this a link?
        self._URL: str=""               # The URL to be used for a link. (This is ignored if _isLink == False.)
                                        # It will be displayed using the localfilename as the link text.
                                        # Note that this is different than the URL method in the other frames


    def __str__(self):      # FanzineTableRow(GridDataRowClass)
        return str(self._cells)

    def __len__(self):     # FanzineTableRow(GridDataRowClass)
        return len(self._cells)

    def Extend(self, s: list[str]) -> None:
        self._cells.extend(s)

    # Make a deep copy of a FanzineTableRow
    def Copy(self) -> FanzineIndexPageTableRow:
        val=FanzineIndexPageTableRow(self._tableColdefs)
        val._cells=[x for x in self._cells]     # Make a new list containing the old cell data
        return val

    # We multiply the cell has by the cell index (+1) so that moves right and left also change the signature
    def Signature(self) -> int:
        return sum([x.__hash__()*(i+1) for i, x in enumerate(self._cells)])


    @property
    def CanDeleteColumns(self) -> bool:
        return True

    # This deletes a single column from the datasource.
    # It must be implemented here because WxDataGrid doesn't understand the details of the DataSource
    def DelCol(self, icol: int) -> None:
        del self._cells[icol]

    @property
    def Cells(self):
        return self._cells
    @Cells.setter
    def Cells(self, val: [str]):
        self._cells=val


    # Get or set a value by name or column number
    #def GetVal(self, name: str|int) -> str|int:
    def __getitem__(self, index: str|int|slice) -> str|list[str]:

        if isinstance(index, int):
            if index < 0 or  index >= len(self._cells):
                raise IndexError
            return self._cells[index]

        assert not isinstance(index, slice)

        assert isinstance(index, str)

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError

        index=self._tableColdefs.index(index)
        return self._cells[index]


    #def SetVal(self, nameOrCol: str|int, val: str|int) -> None:
    def __setitem__(self, index: str | int | slice, value: str | int) -> None:
        if isinstance(value, int):
            value=str(value)    # All data is stored as strings

        if isinstance(index, int):
            if index < 0 or  index >= len(self._cells):
                raise IndexError
            self._cells[index]=value
            return

        assert not isinstance(index, slice)

        assert isinstance(index, str)

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError

        index=self._tableColdefs.index(index)
        self._cells[index]=value
        return


    @property
    def IsLinkRow(self) -> bool:
        return self._isLink
    @IsLinkRow.setter
    def IsLinkRow(self, val: bool) -> None:
        self._isLink=val

    @property
    def IsTextRow(self) -> bool:
        return self._isText
    @IsTextRow.setter
    def IsTextRow(self, val: bool) -> None:
        self._isText=val

    @property
    def IsNormalRow(self) -> bool:
        return not self.IsLinkRow and not self.IsTextRow

    @property
    def IsEmptyRow(self) -> bool:
        return all([cell.strip() == "" for cell in self._cells])