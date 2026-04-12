#!/usr/bin/env python3
"""
Azure AD User Email Enrichment — Veza OAA Enrichment Script

Queries all AzureADUser entities from a Veza tenant, constructs a new custom
attribute called `manager_OAA_idp` by taking each user's `manager_principal_name` and replacing
the domain portion (everything after @) with a configurable IDP domain, then
pushes the enriched values back to Veza via the OAA Enrichment
(entity_enrichment) template.

Data flow:
  Veza (AzureADUser entities)  →  derive manager_OAA_idp = local_part(manager_principal_name) + @IDP_DOMAIN  →  Veza (enriched attribute)
"""

import argparse
import json
import logging
import math
import os
import sys

from typing import Optional

from dotenv import load_dotenv
from oaaclient.client import OAAClient, OAAResponseError

# ---------------------------------------------------------------------------
# Defaults (overridden by .env / CLI args)
# ---------------------------------------------------------------------------

DEFAULT_ENTITY_TYPE = "AzureADUser"
DEFAULT_IDP_DOMAIN = "smurfitwestrock.com"
DEFAULT_PROVIDER_NAME = "Azure Email Enrichment"
DEFAULT_DATA_SOURCE_NAME = "Azure Email Enrichment"
DEFAULT_AZURE_DATASOURCE_NAME: Optional[str] = None
PUSH_BATCH_SIZE = 10_000  # Max entities per push_metadata call to avoid timeouts

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enrichment class
# ---------------------------------------------------------------------------

class AzureEmailEnrichment:
    """
    Queries Veza for all AzureADUser entities, builds a `manager_OAA_idp` value
    from each user's manager_principal_name (replacing the domain), and provides
    a push-ready payload for the OAA Enrichment endpoint.
    """

    def __init__(self, veza_client: OAAClient, idp_domain: str = DEFAULT_IDP_DOMAIN, entity_type: str = DEFAULT_ENTITY_TYPE, azure_datasource_name: Optional[str] = None) -> None:
        self._veza_client = veza_client
        self._idp_domain = idp_domain
        self.entity_type = entity_type
        self._azure_datasource_name = azure_datasource_name
        # Maps entity_id -> {data_source_id, manager_principal_name, manager_OAA_idp}
        self._enriched_users: dict = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process(self) -> None:
        """Query Veza and build the enrichment map."""
        self._query_azure_users()

    def has_enriched_entities(self) -> bool:
        """Return True if at least one user was successfully enriched."""
        return bool(self._enriched_users)

    def get_push_payload(self) -> dict:
        """Return the OAA Enrichment payload dict ready for push_metadata."""
        return {
            "enriched_entity_property_definitions": [
                {
                    "entity_type": self.entity_type,
                    "enriched_properties": {
                        "manager_OAA_idp": "STRING",
                    },
                },
            ],
            "enriched_entities": [
                {
                    "type": self.entity_type,
                    "id": entity_id,
                    "data_source_id": values["data_source_id"],
                    "properties": {
                        "manager_OAA_idp": values["manager_OAA_idp"],
                    },
                }
                for entity_id, values in self._enriched_users.items()
            ],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query_azure_users(self) -> None:
        """Call the Veza query API to fetch all AzureADUser nodes."""

        query = {
            "no_relation": False,
            "include_nodes": True,
            "query_type": "SOURCE_TO_DESTINATION",
            "source_node_types": {
                "nodes": [
                    {
                        "node_type": self.entity_type,
                        "tags_to_get": [],
                        "direct_relationship_only": False,
                    }
                ]
            },
            "node_relationship_type": "EFFECTIVE_ACCESS",
            "result_value_type": "SOURCE_NODES_WITH_COUNTS",
            "include_all_source_tags_in_results": False,
            "include_all_destination_tags_in_results": False,
            "include_sub_permissions": False,
            "include_permissions_summary": True,
        }

        log.info("Querying Veza for all %s entities (page_size=10000)...", self.entity_type)
        # NOTE: oaaclient.api_post auto-paginates (follows has_more / next_page_token)
        # so all entities are returned even if the total exceeds page_size.

        try:
            entities = self._veza_client.api_post(
                api_path="/api/v1/assessments/query_spec:nodes",
                data=query,
                params={"page_size": 10_000},
            )
        except OAAResponseError as exc:
            log.error(
                "Veza query failed: %s — %s (HTTP %s)",
                exc.error,
                exc.message,
                exc.status_code,
            )
            if hasattr(exc, "details"):
                for detail in exc.details:
                    log.error("  Detail: %s", detail)
            sys.exit(1)

        entity_list = entities if isinstance(entities, list) else []
        log.info("Received %d %s entities from Veza", len(entity_list), self.entity_type)

        skipped_no_datasource = 0
        skipped_no_principal_name = 0
        skipped_datasource_mismatch = 0
        datasource_name_found = False

        if self._azure_datasource_name:
            log.info("Filtering entities to Azure datasource: '%s'", self._azure_datasource_name)

        for entity in entity_list:
            entity_id = entity.get("id")
            props = entity.get("properties") or {}

            if not entity_id:
                log.warning("Skipping entity with missing id field: %s", entity)
                continue

            datasource_id = props.get("datasource_id")
            if not datasource_id:
                log.debug("Skipping entity %s: missing datasource_id", entity_id)
                skipped_no_datasource += 1
                continue

            # Filter by Azure datasource name if configured
            if self._azure_datasource_name:
                entity_datasource_name = props.get("datasource_name") or props.get("data_source_name")
                if entity_datasource_name:
                    datasource_name_found = True
                    if entity_datasource_name != self._azure_datasource_name:
                        log.debug("Skipping entity %s: datasource '%s' does not match '%s'", entity_id, entity_datasource_name, self._azure_datasource_name)
                        skipped_datasource_mismatch += 1
                        continue
                elif not datasource_name_found:
                    log.warning("Entity %s has no datasource_name property. Available props: %s", entity_id, list(props.keys()))

            manager_principal_name = props.get("manager_principal_name")
            if not manager_principal_name:
                log.debug("Skipping entity %s: missing manager_principal_name (props: %s)", entity_id, list(props.keys()))
                skipped_no_principal_name += 1
                continue

            # Replace the domain portion of manager_principal_name with the configured IDP domain
            local_part = manager_principal_name.split("@")[0] if "@" in manager_principal_name else manager_principal_name
            manager_oaa_idp = f"{local_part}@{self._idp_domain}"

            self._enriched_users[entity_id] = {
                "data_source_id": datasource_id,
                "manager_principal_name": manager_principal_name,
                "manager_OAA_idp": manager_oaa_idp,
            }

            log.debug("Prepared: entity_id=%s  manager_principal_name=%s  manager_OAA_idp=%s", entity_id, manager_principal_name, manager_oaa_idp)

        if skipped_no_datasource:
            log.warning("Skipped %d entities with no datasource_id", skipped_no_datasource)
        if skipped_no_principal_name:
            log.warning("Skipped %d entities with no manager_principal_name", skipped_no_principal_name)
        if skipped_datasource_mismatch:
            log.info("Skipped %d entities not matching datasource '%s'", skipped_datasource_mismatch, self._azure_datasource_name)
        if self._azure_datasource_name and not datasource_name_found:
            log.warning("No entities had a datasource_name property — datasource filter had no effect. Run with --log-level DEBUG to inspect available properties.")

        log.info(
            "Enrichment ready for %d / %d Azure AD users",
            len(self._enriched_users),
            len(entity_list),
        )


# ---------------------------------------------------------------------------
# Run / push logic
# ---------------------------------------------------------------------------

def run(
    veza_host: str,
    veza_api_key: str,
    idp_domain: str,
    save_json: bool,
    dry_run: bool,
    provider_name: str = DEFAULT_PROVIDER_NAME,
    data_source_name: str = DEFAULT_DATA_SOURCE_NAME,
    provider_id: Optional[str] = None,
    entity_type: str = DEFAULT_ENTITY_TYPE,
    azure_datasource_name: Optional[str] = None,
) -> None:
    """
    Main execution: query users, build enrichment payload, push to Veza.
    """

    log.info("Connecting to Veza at %s", veza_host)
    veza = OAAClient(url=veza_host, api_key=veza_api_key)
    veza.enable_multipart = True  # Safety net for very large enrichment payloads

    enrichment = AzureEmailEnrichment(veza_client=veza, idp_domain=idp_domain, entity_type=entity_type, azure_datasource_name=azure_datasource_name)
    enrichment.process()

    if not enrichment.has_enriched_entities():
        log.warning("No Azure AD users found to enrich — nothing to push.")
        return

    payload = enrichment.get_push_payload()
    entity_count = len(payload["enriched_entities"])
    log.info("Enrichment payload contains %d entities", entity_count)

    if dry_run:
        log.info("[DRY RUN] Skipping Veza push — printing payload preview below.")
        preview = json.dumps(payload, indent=2)
        # Truncate preview so it doesn't flood the terminal
        if len(preview) > 3000:
            preview = preview[:3000] + "\n... (truncated — use --save-json for full output)"
        log.info("[DRY RUN] Payload preview:\n%s", preview)
        return

    # Resolve provider: use explicit ID if given, otherwise lookup/create by name.
    # The enrichment payload references existing entities by their graph IDs.
    if provider_id:
        log.info("Using provider ID from configuration: %s", provider_id)
    else:
        provider = veza.get_provider(name=provider_name)
        if provider:
            provider_id = provider["id"]
            log.info("Using existing enrichment provider '%s' (id: %s)", provider_name, provider_id)
        else:
            provider = veza.create_provider(
                name=provider_name, custom_template="entity_enrichment"
            )
            provider_id = provider["id"]
            log.info("Created enrichment provider '%s' (id: %s)", provider_name, provider_id)

    # Push enrichment data in batches to avoid timeouts / payload size limits.
    # Each batch is pushed to a distinct data source name so that subsequent
    # batches do not overwrite earlier ones (push_metadata replaces the full
    # data source on each call).
    all_entities = payload["enriched_entities"]
    property_defs = payload["enriched_entity_property_definitions"]
    total_batches = math.ceil(entity_count / PUSH_BATCH_SIZE)

    for batch_idx in range(total_batches):
        start = batch_idx * PUSH_BATCH_SIZE
        end = min(start + PUSH_BATCH_SIZE, entity_count)
        batch_entities = all_entities[start:end]

        # Use the original name for single-batch runs; append suffix otherwise
        if total_batches == 1:
            ds_name = data_source_name
        else:
            ds_name = f"{data_source_name} (batch {batch_idx + 1}/{total_batches})"

        batch_payload = {
            "enriched_entity_property_definitions": property_defs,
            "enriched_entities": batch_entities,
        }

        log.info(
            "Pushing batch %d/%d (%d entities) to data source '%s'...",
            batch_idx + 1, total_batches, len(batch_entities), ds_name,
        )

        try:
            veza.push_metadata(
                provider_name=provider_name,
                data_source_name=ds_name,
                metadata=batch_payload,
                save_json=save_json,
            )
        except OAAResponseError as exc:
            log.error(
                "Veza push_metadata failed (batch %d/%d): %s — %s (HTTP %s)",
                batch_idx + 1, total_batches,
                exc.error,
                exc.message,
                exc.status_code,
            )
            if hasattr(exc, "details"):
                for detail in exc.details:
                    log.error("  Detail: %s", detail)
            sys.exit(1)

    log.info(
        "Successfully pushed manager_OAA_idp enrichment for %d Azure AD users to Veza (%d batch%s)",
        entity_count, total_batches, "es" if total_batches > 1 else "",
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich AzureADUser entities in Veza with a derived `manager_OAA_idp` "
            "attribute built from manager_principal_name with domain replacement."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--env-file",
        default=".env",
        metavar="PATH",
        help="Path to a .env file to load (optional).",
    )
    parser.add_argument(
        "--veza-host",
        default=None,
        metavar="HOST",
        help="Veza tenant hostname, e.g. acme.veza.com (or set VEZA_URL).",
    )
    parser.add_argument(
        "--idp-domain",
        default=None,
        metavar="DOMAIN",
        help="IDP domain to replace the existing domain in principal_name (or set IDP_DOMAIN env var).",
    )
    parser.add_argument(
        "--entity-type",
        default=None,
        metavar="TYPE",
        help="Veza entity type to enrich (or set ENTITY_TYPE env var).",
    )
    parser.add_argument(
        "--provider-name",
        default=None,
        metavar="NAME",
        help="Name for the enrichment provider (or set ENRICHMENT_PROVIDER_NAME env var).",
    )
    parser.add_argument(
        "--provider-id",
        default=None,
        metavar="ID",
        help="Existing provider ID to use — skips name-based lookup/creation (or set ENRICHMENT_PROVIDER_ID env var).",
    )
    parser.add_argument(
        "--data-source-name",
        default=None,
        metavar="NAME",
        help="Data source name for the enrichment payload (or set ENRICHMENT_DATA_SOURCE_NAME env var).",
    )
    parser.add_argument(
        "--azure-datasource-name",
        default=None,
        metavar="NAME",
        help="Filter to a specific Azure AD datasource by name — only enrich users from this tenant (or set AZURE_DATASOURCE_NAME env var).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and preview the enrichment payload without pushing to Veza.",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save the enrichment payload to a local JSON file before pushing.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set the logging verbosity level.",
    )

    return parser.parse_args()


def load_config(args: argparse.Namespace) -> dict:
    """Load credentials from .env file then env vars, CLI args take precedence."""
    if args.env_file and os.path.exists(args.env_file):
        load_dotenv(args.env_file)
        log.debug("Loaded env file: %s", args.env_file)

    veza_host = args.veza_host or os.getenv("VEZA_URL") or os.getenv("VEZA_HOST")
    veza_api_key = os.getenv("VEZA_API_KEY")

    missing = []
    if not veza_host:
        missing.append("--veza-host / VEZA_URL")
    if not veza_api_key:
        missing.append("VEZA_API_KEY")

    if missing:
        log.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(2)

    # Resolve all config: CLI arg → env var → hardcoded default
    idp_domain = args.idp_domain or os.getenv("IDP_DOMAIN") or DEFAULT_IDP_DOMAIN
    entity_type = args.entity_type or os.getenv("ENTITY_TYPE") or DEFAULT_ENTITY_TYPE
    provider_name = args.provider_name or os.getenv("ENRICHMENT_PROVIDER_NAME") or DEFAULT_PROVIDER_NAME
    provider_id = args.provider_id or os.getenv("ENRICHMENT_PROVIDER_ID") or None
    data_source_name = args.data_source_name or os.getenv("ENRICHMENT_DATA_SOURCE_NAME") or DEFAULT_DATA_SOURCE_NAME
    azure_datasource_name = args.azure_datasource_name or os.getenv("AZURE_DATASOURCE_NAME") or None

    return {
        "veza_host": veza_host,
        "veza_api_key": veza_api_key,
        "idp_domain": idp_domain,
        "entity_type": entity_type,
        "provider_name": provider_name,
        "provider_id": provider_id,
        "data_source_name": data_source_name,
        "azure_datasource_name": azure_datasource_name,
    }


def main() -> None:
    print(
        "\n"
        "  ╔══════════════════════════════════════════════════════════╗\n"
        "  ║   Azure AD → Veza  |  OAA IDP Enrichment  v1.1         ║\n"
        "  ║   Attribute: manager_OAA_idp = manager_principal_name + IDP  ║\n"
        "  ╚══════════════════════════════════════════════════════════╝\n"
    )

    args = parse_args()

    log.setLevel(getattr(logging, args.log_level))

    config = load_config(args)

    run(
        veza_host=config["veza_host"],
        veza_api_key=config["veza_api_key"],
        idp_domain=config["idp_domain"],
        save_json=args.save_json,
        dry_run=args.dry_run,
        provider_name=config["provider_name"],
        data_source_name=config["data_source_name"],
        provider_id=config["provider_id"],
        entity_type=config["entity_type"],
        azure_datasource_name=config["azure_datasource_name"],
    )

    log.info("Azure AD manager_OAA_idp enrichment completed.")


if __name__ == "__main__":
    main()
