class BasePlugin:

    action = None
    required_parameters = {}
    missing_parameter_message = "Required parameters are missing."

    def validate_parameters(self, parameters):
        parameters = parameters or {}

        for parameter_name, error_message in self.required_parameters.items():
            value = parameters.get(parameter_name)

            if value is None:
                return error_message

            if isinstance(value, str) and not value.strip():
                return error_message

        return None

    def execute(self, parameters):
        raise NotImplementedError
