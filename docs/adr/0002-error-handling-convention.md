# ADR 0002: Error Handling Convention - Result Types vs Exceptions

## Status
Accepted - Stage 04

## Context

In a system that integrates with external services (AI providers, messaging channels),
we need a consistent way to handle failures. There are two main approaches:

1. **Exceptions**: Use Python's exception mechanism for all errors
2. **Result Types**: Use a functional approach with `Result[T, E]` for expected failures

The challenge is distinguishing between:
- **Expected failures**: Can happen in normal operation (network issues, rate limits, validation errors)
- **Unexpected failures**: Indicates a bug in the code (programming errors, invariants violated)

## Decision

Adopt a **hybrid approach**:

- **Use `Result[T, E]` for expected failures** at boundaries
- **Use exceptions for programming errors (bugs)**

### When to Use Result Types

Use `Result` types for expected failures in these scenarios:

1. **External Service Calls**: Model providers, channel adapters, external APIs
   - Network timeouts
   - Rate limiting
   - Authentication failures
   - Service unavailable

2. **Validation**: Input validation, parsing, data transformation
   - Invalid user input
   - Missing required fields
   - Type mismatches

3. **Business Logic**: Domain-level failures that are part of normal operation
   - Not found errors
   - Permission denied
   - Resource conflicts

### When to Use Exceptions

Use exceptions for programming errors (bugs):

1. **Invariant Violations**: Preconditions, postconditions, assertions
2. **Internal State Errors**: Impossible states, null pointer dereferences
3. **Type Errors**: Type mismatches that should never happen with proper typing
4. **Implementation Bugs**: Logic errors, incorrect algorithm implementation

### Error Type Hierarchy

```python
# Domain exceptions (for bugs)
class DomainError(Exception):
    """Base exception for domain errors (bugs)."""
    pass

class ValidationError(DomainError):
    """Raised when domain validation fails."""
    pass

class NotFoundError(DomainError):
    """Raised when a domain entity is not found."""
    pass

class InvariantError(DomainError):
    """Raised when a domain invariant is violated."""
    pass

# Result types (for expected failures)
@dataclass(frozen=True)
class Error:
    """Value object for expected failures."""
    code: str
    message: str
    details: dict | None = None

@dataclass(frozen=True)
class Result(Generic[T, E]):
    """Functional result type."""
    value: T | None = None
    error: E | None = None
```

### Conversion at Boundaries

At adapter boundaries, convert provider-specific exceptions to `Result` types:

```python
# In an adapter
async def generate(self, prompt: str) -> Result[str, Error]:
    try:
        response = await self.client.generate(prompt)
        return Result.ok(response)
    except RateLimitError as e:
        return Result.err(Error.rate_limit("model_provider", retry_after=e.retry_after))
    except TimeoutError as e:
        return Result.err(Error.timeout("model_provider", e.timeout))
    except Exception as e:
        # Unexpected error - log and convert to error
        logger.error("Unexpected error in model adapter", error=str(e))
        return Result.err(Error.provider_error("model_provider", str(e)))
```

## Consequences

### Positive

1. **Explicit Error Handling**: Callers must explicitly handle expected failures
2. **No Hidden Exceptions**: Expected failures are part of the type signature
3. **Better Testing**: Can test both success and failure paths easily
4. **Clear Intent**: Distinguishes between "this can fail" and "this should never fail"
5. **Composition**: Result types compose well with functional patterns (map, flat_map)

### Negative

1. **Boilerplate**: More code to handle Result types vs exceptions
2. **Learning Curve**: Team needs to understand the pattern
3. **Not Idiomatic**: Python traditionally uses exceptions for all errors

### Trade-offs

- **Not Absolute**: We don't use Result types for every function. Only at boundaries where
  failures are expected and part of normal operation.
- **Gradual Adoption**: Can introduce Result types incrementally at critical boundaries
- **Interoperability**: Need to convert between Result and exceptions at layer boundaries

## Alternatives Considered

### 1. Exceptions Only
**Rejected**: Can't distinguish between expected and unexpected failures.
All errors look the same, making it hard to write robust error handling.

### 2. Result Types Only
**Rejected**: Too much boilerplate for internal errors that should never happen.
Exceptions are more appropriate for bugs.

### 3. Custom Exception Hierarchy Only
**Rejected**: Doesn't provide the functional benefits of Result types.
Still can't compose error handling easily.

### 4. Either/Maybe Types
**Rejected**: Similar to Result types but less explicit about error handling.

## References

- [Rust's Result Type](https://doc.rust-lang.org/std/result/)
- [Functional Error Handling in Python](https://medium.com/@cscorley/functional-error-handling-in-python-7e985638638)
- [The Error Model](https://lexi-lambda.github.io/blog/2019/11/05/the-error-model/)
