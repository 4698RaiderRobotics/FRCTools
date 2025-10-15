from dataclasses import dataclass

# Timing belt geometery information can be found in the docs/references folder
#
#   

@dataclass
class TimingBeltGeom :
        # All dimension in millimeters
    name: str
    pitchLength: float          # The Pitch of the belt (e.g. 5mm or 3mm)
    thickness: float            # The thickness of the belt without the tooth height
    width: float                # Preferred width 
    pitchLineDepth: float       # Distance from inside of belt to pitch line
    toothHeight: float          # Total height of the tooth
    filletRadius: float         # The fillet at the base of the tooth root
    toothBumpRadius: float      # The radius of the tooth bump
 

belt_geometry = [
    TimingBeltGeom( 
        name = 'HTD 5mm',
        pitchLength = 5,
        thickness = 1.74,
        width = 15,
        pitchLineDepth = 0.5715,    
        toothHeight = 2.06,
        filletRadius = 0.43,
        toothBumpRadius = 1.49,
    ),
    TimingBeltGeom( 
        name = 'GT2 3mm',
        pitchLength = 3,
        thickness = 1.26,
        width = 9,
        pitchLineDepth = 0.381,    
        toothHeight = 1.14,
        filletRadius = 0.35,
        toothBumpRadius = 0.85,
    ),
    TimingBeltGeom( 
        name = 'RT25',
        pitchLength = 0.25 * 25.4,
        thickness = 1.27,
        width = 0.5 * 25.4,
        pitchLineDepth = 0.56,    
        toothHeight = 2.41,
        filletRadius = 0.53,
        toothBumpRadius = 1.8,
    ),
    TimingBeltGeom( 
        name = '#25H Chain',
        pitchLength = 0.25 * 25.4,
        thickness = 0.358 * 25.4,
        width = 0.463 * 25.4,
        pitchLineDepth = 0,    
        toothHeight = 0,
        filletRadius = 0,
        toothBumpRadius = 0,
    ),
    TimingBeltGeom( 
        name = '#35 Chain',
        pitchLength = 0.375 * 25.4,
        thickness = 0.236 * 25.4,
        width = 0.354 * 25.4,
        pitchLineDepth = 0,    
        toothHeight = 0,
        filletRadius = 0,
        toothBumpRadius = 0,
    )
]

