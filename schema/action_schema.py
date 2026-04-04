class ActionSchema:

    def __init__(self, action, resource, device="local", parameters=None):

        self.action = action
        self.resource = resource
        self.device = device
        self.parameters = parameters or {}