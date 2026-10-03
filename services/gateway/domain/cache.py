from typing import Dict


class CacheKey:
    @staticmethod
    def mapped_route(
        service_name: str,
        ingress_path: str
    ) -> str:
        '''
        Cache key for a resolved ingress -> service route.

        Deliberately keyed on the route rule only, not on the route's parameter
        values: the mapping resolves from static configuration and is identical
        for every value of a segment.  Including the values produced one entry
        per distinct value -- unbounded, caller-driven growth holding the same
        string over and over.
        '''

        return f'api-gateway-{service_name}-{ingress_path}'
