from typing import Dict


class CacheKey:
    @staticmethod
    def mapped_route(
        ingress_path: str,
        kwargs: Dict
    ) -> str:
        return f'api-gateway-{ingress_path}-{kwargs}'
