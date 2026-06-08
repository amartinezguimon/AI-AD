"""VisionMetrics AI — productized monorepo.

Layout:
    edge/    code that runs in the store (the agent + calibration)
    cloud/   code that runs on the server VM (ingest, api, worker)
    web/     the SaaS dashboard
    shared/  the edge<->cloud data contract (single source of truth)
    ml/      offline model training & evaluation

The legacy prototype still lives under ../src and ../*.py; modules here are
extracted from it incrementally, behavior-preserving, with unit tests.
"""

__version__ = "0.1.0"
