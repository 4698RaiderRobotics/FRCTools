import adsk.core
import adsk.fusion
from ...lib import fusionAddInUtils as futil
from .entry import motionTypes, motionTypesDefault, pinionCenters, pinionGears, pinionTeeth
from . import CCLine
from . import CCLineUtils as ccutil

app = adsk.core.Application.get()
ui = app.userInterface

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
# local_handlers = []

class Dialog :
    # Dialog constructor
    def __init__( self, inputs: adsk.core.CommandInputs, isCreateDialog: bool ) :

        self.isCreateDialog = isCreateDialog

                # Motion Component Type
        self.motionType = inputs.addDropDownCommandInput('motion_type', 'Motion Type', adsk.core.DropDownStyles.TextListDropDownStyle)
        for mtype in motionTypes:
            self.motionType.listItems.add( mtype, True, '')
        self.motionType.listItems.item( motionTypesDefault ).isSelected = True

        # # Create a selection input.
        if self.isCreateDialog:
            self.curveSelection = inputs.addSelectionInput('curve_selection', 'Selection', 'Select a circle, or a center point')
            self.curveSelection.addSelectionFilter( "SketchCircles" )
            # curveSelection.addSelectionFilter( "SketchLines" )
            self.curveSelection.addSelectionFilter( "SketchPoints" )
            self.curveSelection.setSelectionLimits( 1, 1 )
            self.requireSelection = inputs.addBoolValueInput( "require_selection", "Require Selection", True, "", True )
        else:
            self.curveSelection = inputs.addSelectionInput('curve_selection', 'Selection', 'Select a C-C Distance object')
            self.curveSelection.setSelectionLimits( 3, 3 )
            self.requireSelection = None



        # Create a separator.
        self.selectSep = inputs.addSeparatorCommandInput( "selection_cog1_sep")

        # Create a integer spinners for cog1 and pinion options.
        self.cog1Teeth = inputs.addIntegerSpinnerCommandInput('cog1_teeth', 'Cog #1 Teeth', 6, 100, 1, 24)
        self.cog1Group = inputs.addGroupCommandInput('use_pinion_cog1', 'Use Pinion')
        self.cog1Group.isExpanded = False
        self.cog1Group.isEnabledCheckBoxDisplayed = True
        self.cog1Group.isEnabledCheckBoxChecked = False
        groupChildInputs = self.cog1Group.children
        self.cog1Pinion = groupChildInputs.addDropDownCommandInput('pinion_cog1', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
        for gear in pinionGears:
             self.cog1Pinion.listItems.add( gear, True, '')


        # Create a integer spinners for cog1 and pinion options.
        self.cog2Teeth = inputs.addIntegerSpinnerCommandInput('cog2_teeth', 'Cog #2 Teeth', 6, 100, 1, 36)
        self.cog2Group = inputs.addGroupCommandInput('use_pinion_cog2', 'Use Pinion')
        self.cog2Group.isExpanded = False
        self.cog2Group.isEnabledCheckBoxDisplayed = True
        self.cog2Group.isEnabledCheckBoxChecked = False
        groupChildInputs = self.cog2Group.children
        self.cog2Pinion = groupChildInputs.addDropDownCommandInput('pinion_cog2', 'Pinion Gear', adsk.core.DropDownStyles.TextListDropDownStyle)
        for gear in pinionGears:
            self.cog2Pinion.listItems.add( gear, True, '')

        self.swapCogs = inputs.addBoolValueInput( "swap_cogs", "Swap Cogs", True )

        self.beltTeeth = inputs.addIntegerSpinnerCommandInput( "belt_teeth", "Belt Teeth", 35, 400, 1, 70 )
        self.beltTeeth.isVisible = False

        self.chainLinks = inputs.addIntegerSpinnerCommandInput( "chain_links", "Chain Links", 25, 400, 2, 60 )
        self.chainLinks.isVisible = False

        # Create a value input field and set the default using 1 unit of the default length unit.
        defaultLengthUnits = "in"
        default_value = adsk.core.ValueInput.createByString('0.003')
        self.extraCenter = inputs.addValueInput('extra_center', 'Extra Center', defaultLengthUnits, default_value)

        # Create a separator.
        inputs.addSeparatorCommandInput( "message_sep")
        self.status = inputs.addTextBoxCommandInput( "status_msg", "", "Select", 1, True )

        self.ignorePinions = False

    def load_inputs( self, inputs: adsk.core.CommandInputs ):

        self.motionType: adsk.core.DropDownCommandInput = inputs.itemById('motion_type')
        self.curveSelection: adsk.core.SelectionCommandInput = inputs.itemById('curve_selection')
        self.requireSelection: adsk.core.BoolValueCommandInput = inputs.itemById( "require_selection" )
        self.selectSep: adsk.core.SeparatorCommandInput = inputs.itemById( "selection_cog1_sep")
        self.cog1Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog1_teeth')
        self.cog1Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog1')
        self.cog1Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog1')
        self.cog2Teeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('cog2_teeth')
        self.cog2Group: adsk.core.GroupCommandInput = inputs.itemById('use_pinion_cog2')
        self.cog2Pinion: adsk.core.DropDownCommandInput = inputs.itemById('pinion_cog2')
        self.beltTeeth: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "belt_teeth" )
        self.chainLinks: adsk.core.IntegerSpinnerCommandInput = inputs.itemById( "chain_links" )
        self.extraCenter: adsk.core.ValueInput = inputs.itemById('extra_center')
        self.swapCogs: adsk.core.BoolValueCommandInput = inputs.itemById( "swap_cogs" )
        self.status: adsk.core.TextBoxCommandInput = inputs.itemById('status_msg')

    # This event handler is called when the user changes anything in the command dialog
    # allowing you to modify values of other inputs based on that change.
    def input_changed( self, args: adsk.core.InputChangedEventArgs ):
        changed_input = args.input

        # # General logging for debug.
        futil.log(f'{args.firingEvent.name} input_changed() from a change to {changed_input.id}')

        self.load_inputs( args.input.parentCommand.commandInputs )

        if changed_input.id == 'curve_selection' and not self.isCreateDialog:
            # Check if there is no selection and disable the dialog 
            if self.curveSelection.selectionCount == 0:
                self.disable_dialog()
        
        if changed_input.id == 'motion_type':
            self.ignorePinions = False
            if self.motionType.selectedItem.index == 0:  
                # Gear type is selected
                self.extraCenter.value = 0.003 * 2.54
                self.cog1Group.isVisible = True
                self.cog2Group.isVisible = True
                self.beltTeeth.isVisible = False
                self.chainLinks.isVisible = False
            else:
                # Non-gear type is selected
                self.extraCenter.value = 0
                self.cog1Teeth.isVisible = True
                self.cog1Group.isVisible = False
                self.cog1Group.isEnabledCheckBoxChecked = False
                self.cog2Teeth.isVisible = True
                self.cog2Group.isVisible = False
                self.cog2Group.isEnabledCheckBoxChecked = False
                if self.beltTeeth.value == 0 :
                    self.beltTeeth.value = 70
                if self.chainLinks.value == 0 :
                    self.chainLinks.value = 60
                if self.motionType.selectedItem.index < 4:
                    self.beltTeeth.isVisible = True
                    self.chainLinks.isVisible = False
                else:
                    self.beltTeeth.isVisible = False
                    self.chainLinks.isVisible = True


        if changed_input.id == 'require_selection':
            if self.requireSelection.value:
                self.curveSelection.isVisible = True
                self.curveSelection.setSelectionLimits( 1, 2 )
            else:
                self.curveSelection.isVisible = False
                self.curveSelection.clearSelection()
                self.curveSelection.setSelectionLimits( 0, 2 )

        if changed_input.id == 'use_pinion_cog1' and self.cog1Group.isEnabledCheckBoxDisplayed:
            if self.cog1Group.isEnabledCheckBoxChecked:
                # We are using a pinion for cog 1
                self.ignorePinions = False
                self.cog1Teeth.isVisible = False
                self.cog1Teeth.value = pinionCenters[ self.cog1Pinion.selectedItem.index ]
            else:
                # We are not using a pinion 
                self.cog1Teeth.isVisible = True
                self.cog1Teeth.value = 20

        if changed_input.id == 'pinion_cog1':
            self.cog1Teeth.value = pinionCenters[ self.cog1Pinion.selectedItem.index ]


        if changed_input.id == 'use_pinion_cog2' and self.cog2Group.isEnabledCheckBoxDisplayed:
            if self.cog2Group.isEnabledCheckBoxChecked:
                # We are using a pinion for cog 2
                self.ignorePinions = False
                self.cog2Teeth.isVisible = False
                self.cog2Teeth.value = pinionCenters[ self.cog2Pinion.selectedItem.index ]
            else:
                # We are not using a pinion 
                self.cog2Teeth.isVisible = True
                self.cog2Teeth.value = 20

        if changed_input.id == 'pinion_cog2':
            self.cog2Teeth.value = pinionCenters[ self.cog2Pinion.selectedItem.index ]

        if changed_input.id == 'cog1_teeth' and self.motionType.selectedItem.index == 0 :
            # If cog teeth are set below 17 teeth then ask if user wants to use pinions
            if self.cog1Teeth.value < 17 and self.cog1Teeth.value > 5 and not self.cog1Group.isEnabledCheckBoxChecked:
                if not self.ignorePinions:
                    self.ignorePinions = not futil.yes_no_message( 'Do you want to switch to Pinion Gears?' )
                if not self.ignorePinions:
                    self.cog1Group.isEnabledCheckBoxChecked = True
                    self.cog1Teeth.isVisible = False

        if changed_input.id == 'cog2_teeth' and self.motionType.selectedItem.index == 0 :
            # If cog teeth are set below 17 teeth then ask if user wants to use pinions
            if self.cog2Teeth.value < 17 and self.cog2Teeth.value > 5 and not self.cog2Group.isEnabledCheckBoxChecked:
                if not self.ignorePinions:
                    self.ignorePinions = not futil.yes_no_message( 'Do you want to switch to Pinion Gears?' )
                if not self.ignorePinions:
                    self.cog2Group.isEnabledCheckBoxChecked = True
                    self.cog2Teeth.isVisible = False


    # This event handler is called when the user interacts with any of the inputs in the dialog
    # which allows you to verify that all of the inputs are valid and enables the OK button.
    def validate_input( self, args: adsk.core.ValidateInputsEventArgs ):

        logstr = f'{args.firingEvent.name} validate_input: Motion={self.motionType.selectedItem.index}, '
        logstr += f'N1={self.cog1Teeth.value}, N2={self.cog2Teeth.value}, T={self.beltTeeth.value}'
        futil.log( logstr )

        self.load_inputs( args.inputs )

        args.areInputsValid = True        

        if not (self.cog1Teeth.value >= 6 and self.cog1Teeth.value < 100 and self.cog2Teeth.value >= 6 and self.cog1Teeth.value < 100 ):
            self.set_status( 'Invalid Number of cog teeth! [6-100]</font></div>', True )
            args.areInputsValid = False
            return
        
        if self.motionType.selectedItem.index != 0:
            ld = CCLine.CCLineData()
            ld.motion = self.motionType.selectedItem.index
            ld.N1 = self.cog1Teeth.value
            ld.N2 = self.cog2Teeth.value
            ld.Teeth = self.beltTeeth.value
            ld.Links = self.chainLinks.value
            ccutil.calcCCLineData( ld )

            if ld.ccDistIN < (ld.OD1 + ld.OD2) / 2.0 :
                # belt/chain is too short
                if ld.motion < 4:
                    self.set_status( 'Belt is too short! (cc-dist={:.3f})'.format(ld.ccDistIN), True )
                else:
                    self.set_status( 'Chain is too short! (cc-dist={:.3f})'.format(ld.ccDistIN), True )
                args.areInputsValid = False
                return


    def generate_ccline_data( self ) -> CCLine.CCLineData :
        ld = CCLine.CCLineData()

        ld.motion = self.motionType.selectedItem.index
        ld.ExtraCenterIN = self.extraCenter.value / 2.54
        ld.Teeth = int( self.beltTeeth.value )
        ld.Links = int( self.chainLinks.value )
        ld.N1 = int( self.cog1Teeth.value )
        if self.cog1Group.isEnabledCheckBoxChecked :
            ld.PIN1 = pinionTeeth[ self.cog1Pinion.selectedItem.index ]
        else:
            ld.PIN1 = 0
        ld.N2 = int( self.cog2Teeth.value )
        if self.cog2Group.isEnabledCheckBoxChecked :
            ld.PIN2 = pinionTeeth[ self.cog2Pinion.selectedItem.index ]
        else:
            ld.PIN2 = 0

        if self.swapCogs.value :
            tempN = ld.N1
            ld.N1 = ld.N2
            ld.N2 = tempN
            tempN = ld.PIN1
            ld.PIN1 = ld.PIN2
            ld.PIN2 = tempN

        self.set_status( ccutil.createLabelString( ld ), False )

        return ld


    def disable_dialog( self ):

        self.motionType.isEnabled = False
        self.selectSep.isEnabled = False
        self.cog1Teeth.isEnabled = False
        self.cog1Group.isEnabled = False
        self.cog1Group.isEnabledCheckBoxDisplayed = False
        self.cog2Teeth.isEnabled = False
        self.cog2Group.isEnabled = False
        self.cog2Group.isEnabledCheckBoxDisplayed = False
        self.beltTeeth.isEnabled = False
        self.extraCenter.isEnabled = False
        self.swapCogs.isEnabled = False
        self.set_status( 'Select a C-C Distance object.', False )

    def initialize_dialog( self, lineData: CCLine.CCLineData ):

        self.motionType.isEnabled = True
        self.selectSep.isEnabled = True
        self.cog1Teeth.isEnabled = True
        self.cog1Group.isEnabled = True
        self.cog1Group.isEnabledCheckBoxDisplayed = True
        self.cog2Teeth.isEnabled = True
        self.cog2Group.isEnabled = True
        self.cog2Group.isEnabledCheckBoxDisplayed = True
        self.beltTeeth.isEnabled = True
        self.extraCenter.isEnabled = True
        self.swapCogs.isEnabled = True

        self.cog1Teeth.value = lineData.N1
        self.cog2Teeth.value = lineData.N2
        if lineData.PIN1 > 0 :
            self.cog1Group.isEnabledCheckBoxChecked = True
            self.cog1Teeth.isVisible = False
            if lineData.N1 < 14:
                idx = lineData.PIN1 - 8
            elif lineData.N1 < 16:
                idx = lineData.PIN1 - 7
            else:
                idx = lineData.PIN1 - 6
            self.cog1Pinion.listItems.item( idx ).isSelected = True

        if lineData.PIN2 > 0 :
            self.cog2Group.isEnabledCheckBoxChecked = True
            self.cog2Teeth.isVisible = False
            if lineData.N2 < 14:
                idx = lineData.PIN2 - 8
            elif lineData.N2 < 16:
                idx = lineData.PIN2 - 7
            else:
                idx = lineData.PIN2 - 6
            self.cog2Pinion.listItems.item( idx ).isSelected = True

        if lineData.motion == 0 :
            self.beltTeeth.isVisible = False
            self.chainLinks.isVisible = False
            self.cog1Group.isVisible = True
            self.cog2Group.isVisible = True
        elif lineData.motion < 4:
            self.beltTeeth.value = lineData.Teeth
            self.beltTeeth.isVisible = True
            self.chainLinks.isVisible = False
            self.cog1Group.isVisible = False
            self.cog2Group.isVisible = False
        else:
            self.chainLinks.value = lineData.Links
            self.beltTeeth.isVisible = False
            self.chainLinks.isVisible = True
            self.cog1Group.isVisible = False
            self.cog2Group.isVisible = False

        self.extraCenter.value = lineData.ExtraCenterIN * 2.54
        self.motionType.listItems.item( lineData.motion ).isSelected = True

        self.set_status( ccutil.createLabelString( lineData ), False )

    def set_status( self, str, isError: bool ) :
        if isError:
            msg = f'<div align="center"><font color="red">{str}</font></div>'
        else:
            msg = f'<div align="center">{str}</div>'

        self.status.formattedText = msg
