from tplinksmartplug.TPLinkSmartPlug import SmartPlug

# load configuration
sp = SmartPlug('../tplinksmartplug/configuration.json')
# load device info
sp.setup_devices()
# get current state of smart plug  with alias'Sudoplug'
state = sp.get_state('Sudoplug')
# set opposite state
sp.set_state('Sudoplug', not state)
