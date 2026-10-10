"""Explicitly separate outcomes, requests and user actions."""
from app.contracts.api_usage import Summary

API_FAILURES = frozenset({'retryable', 'failed', 'permanent', 'channel', 'rejected'})
CLI_SUCCESSES = frozenset({'candidate', 'adopted', 'waiting_user', 'succeeded'})
CLI_FAILURES = frozenset({'failed', 'cancelled', 'timeout'})
API_EDITS = frozenset({'image_edit', 'text_edit', 'text_repair', 'revision'})


def generation_type(fact: dict) -> str | None:
    category = fact['category']
    if fact['channel'] == 'cli' and category in ('cli_submission', 'cli_round', 'cli_candidate'):
        return 'cli_edit'
    if fact['channel'] == 'api' and category in ('api_request', 'version_published'):
        if fact['kind'] == 'generation':
            return 'initial'
        if fact['kind'] in API_EDITS:
            return 'api_edit'
    return None


def generated_images(fact: dict) -> int:
    # A request/round/action is not an image. CLI adoption never adds another output.
    if fact['state'] != 'succeeded' or fact['category'] not in ('version_published', 'cli_candidate'):
        return 0
    return fact['quantity'] if generation_type(fact) else 0


def summarize(facts: list[dict]) -> Summary:
    result = Summary()
    generated_tasks = set()
    counters = {
        'task_created': 'tasksCreated', 'cli_submission': 'cliSubmitted',
        'cli_candidate': 'cliCandidates',
        'adopt': 'adoptions', 'restore': 'restores',
    }
    for fact in facts:
        category, state, quantity = fact['category'], fact['state'], fact['quantity']
        images = generated_images(fact)
        if images:
            generated_tasks.add(fact['task_id'])
            if generation_type(fact) == 'initial':
                result.initialImages += images
            else:
                result.modifiedImages += images
        if fact['attribution'] != 'verified':
            result.unverifiedAttribution += 1
        if category in counters:
            field = counters[category]
            setattr(result, field, getattr(result, field) + quantity)
        elif category == 'version_published':
            if fact['channel'] == 'unknown':
                result.unverifiedVersions += quantity
            else:
                result.generatedVersions += quantity
        elif category == 'api_request':
            result.apiAttempts += quantity
            if state == 'succeeded':
                result.apiSucceeded += quantity
            elif state in API_FAILURES:
                result.apiFailed += quantity
            elif state == 'running':
                result.apiRunning += quantity
            else:
                result.apiUnknown += quantity
            if fact['is_retry'] is True:
                result.apiRetries += quantity
            elif fact['is_retry'] is None:
                result.apiRetryUnknown += quantity
        elif category == 'cli_round':
            if state == 'unverified' or not quantity:
                result.cliUnverified += 1
                continue
            result.cliStarted += quantity
            if state in CLI_SUCCESSES:
                result.cliSucceeded += quantity
            elif state in CLI_FAILURES:
                result.cliFailed += quantity
            else:
                result.cliUnknown += quantity
    known = result.apiSucceeded + result.apiFailed
    result.requestSuccessRate = result.apiSucceeded / known if known else None
    result.totalGeneratedImages = result.initialImages + result.modifiedImages
    result.generatedTasks = len(generated_tasks)
    return result
