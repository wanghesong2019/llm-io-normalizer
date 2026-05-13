class LLMGatewayError(RuntimeError):
    """Base gateway error."""


class LLMEmptyOutputError(LLMGatewayError):
    """The provider returned HTTP success but no usable final answer."""


class LLMProviderError(LLMGatewayError):
    """The provider call failed."""
