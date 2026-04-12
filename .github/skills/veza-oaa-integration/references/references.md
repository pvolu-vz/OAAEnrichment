# Reference Materials

Fetch these before writing any code:

- **OAA Python SDK docs**: https://docs.veza.com/4yItIzMvkpAvMVFAamTf/developers/api/oaa/python-sdk
- **OAA Getting Started**: https://docs.veza.com/4yItIzMvkpAvMVFAamTf/developers/api/oaa/getting-started
- **OAA Templates overview**: https://docs.veza.com/4yItIzMvkpAvMVFAamTf/developers/api/oaa/templates
- **Custom application templates**: https://docs.veza.com/4yItIzMvkpAvMVFAamTf/developers/api/oaa/templates#custom-application-templates
- **Custom Identity Provider templates**: https://docs.veza.com/4yItIzMvkpAvMVFAamTf/developers/api/oaa/templates#custom-identity-provider-templates
- **Reference — resources/sub-resources pattern**: https://github.com/pvolu-vz/NetApp (`netAppShares.py`, `install_ontap.sh`, `requirements.txt`, `.env.example-ontap`)
- **Reference — HR/API sources pattern**: https://github.com/pvolu-vz/adp_project (`adp_api.py`, `adp_OAA_veza.sh`, `requirements.txt`, `config.py`, `util.py`, `.env`)

## Community Connector Examples

Real-world OAA connectors from https://github.com/Veza/oaa-community/tree/main/connectors — study these before building a new connector:

| Connector | Main Script | Pattern / Notes |
|-----------|-------------|-----------------|
| **GitHub** | [`oaa_github.py`](https://github.com/Veza/oaa-community/blob/main/connectors/github/oaa_github.py) | CustomApplication; maps org → app, members → local users, teams → local groups, repos → resources; GitHub App (PEM key) auth; supports user CSV identity map |
| **Jira Cloud** | [`oaa_jira.py`](https://github.com/Veza/oaa-community/blob/main/connectors/jira/oaa_jira.py) | CustomApplication; maps Jira instance → app, projects → resources, groups → local groups, project roles → local groups; Atlassian API token auth |
| **Slack** | [`oaa_slack.py`](https://github.com/Veza/oaa-community/blob/main/connectors/slack/oaa_slack.py) | CustomApplication; maps workspace → app, users → local users, user groups → local groups; Slack OAuth token auth; custom properties for MFA, guest status |
| **GitLab** | [`connectors/gitlab/`](https://github.com/Veza/oaa-community/tree/main/connectors/gitlab) | CustomApplication; similar org/project/member pattern to GitHub connector |
| **Bitbucket Cloud** | [`connectors/bitbucket-cloud/`](https://github.com/Veza/oaa-community/tree/main/connectors/bitbucket-cloud) | CustomApplication; maps Bitbucket workspace/repos/users/groups |
| **Looker** | [`connectors/looker/`](https://github.com/Veza/oaa-community/tree/main/connectors/looker) | CustomApplication; maps Looker users, groups, and content permissions |
| **PagerDuty** | [`connectors/pagerduty/`](https://github.com/Veza/oaa-community/tree/main/connectors/pagerduty) | CustomApplication; maps PagerDuty users, teams, and service permissions |
| **Rollbar** | [`connectors/rollbar/`](https://github.com/Veza/oaa-community/tree/main/connectors/rollbar) | CustomApplication; maps Rollbar projects, teams, and user access levels |
| **Cerby** | [`connectors/cerby/`](https://github.com/Veza/oaa-community/tree/main/connectors/cerby) | CustomApplication; maps Cerby managed app accounts and permissions |

### Common structure across all community connectors

Each connector follows this layout:
```
oaa_<name>.py       # main connector script
requirements.txt    # pinned deps (oaaclient, requests, etc.)
Dockerfile          # optional container build
README.md           # setup, parameters table, OAA mapping table
.gitignore
```

Key patterns to replicate:
- Accept all secrets via **environment variables** with CLI flag overrides
- Include a `--save-json` / `--debug` flag pair
- Print a mapping table comment in the README showing how source entities map to OAA types (Application, Local User, Local Group, Local Role, Application Resource)
- Use `oaaclient.client.OAAClient` to push; handle `OAAClientError` and log properly

### Query Data from existing Veza tenant

if need to query data from Veza tenant read this first:
- https://docs.veza.com/4yItIzMvkpAvMVFAamTf/developers/api/query-builder/getassessmentquerynodes

use the below as example for querying data from Veza:

```
def query_veza_entity(search_value, property_name, entity_type, veza_url, veza_api_key):
    """
    Query Veza to find an entity by property value
    
    Args:
        search_value: Value to search for (email, account_name, etc.)
        property_name: Property to search on ('email', 'account_name', 'idp_unique_id')
        entity_type: Type of entity to search for (e.g., 'ActiveDirectoryUser')
        veza_url: Veza instance URL
        veza_api_key: Veza API key
    
    Returns:
        dict: Entity details with 'id' and 'type' keys, or None if not found or multiple found
    """
    url = f"https://{veza_url}/api/v1/assessments/query_spec:nodes"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {veza_api_key}'
    }
    
    # Build query payload based on property type
    # For email searches, check both email and idp_unique_id
    if property_name == 'email':
        condition_specs = [
            {
                "property": "email",
                "fn": "EQ",
                "value": search_value,
                "not": False
            },
            {
                "property": "idp_unique_id",
                "fn": "EQ",
                "value": search_value,
                "not": False
            }
        ]
        child_expressions = [
            {
                "operator": "OR",
                "specs": condition_specs,
                "tag_specs": [],
                "child_expressions": []
            }
        ]
    else:
        # For other properties, simple equality check
        condition_specs = []
        child_expressions = [
            {
                "operator": "OR",
                "specs": [
                    {
                        "property": property_name,
                        "fn": "EQ",
                        "value": search_value,
                        "not": False
                    }
                ],
                "tag_specs": [],
                "child_expressions": []
            }
        ]
    
    payload = {
        "no_relation": False,
        "include_nodes": True,
        "query_type": "SOURCE_TO_DESTINATION",
        "source_node_types": {
            "nodes": [
                {
                    "node_type": entity_type,
                    "tags_to_get": [],
                    "condition_expression": {
                        "operator": "AND",
                        "specs": [],
                        "tag_specs": [],
                        "child_expressions": child_expressions
                    },
                    "direct_relationship_only": False
                }
            ]
        },
        "node_relationship_type": "EFFECTIVE_ACCESS",
        "result_value_type": "SOURCE_NODES_WITH_COUNTS",
        "include_all_source_tags_in_results": False,
        "include_all_destination_tags_in_results": False,
        "include_sub_permissions": False,
        "include_permissions_summary": True
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        
        values = result.get('values', [])
        
        if len(values) == 0:
            logger.error(f"No {entity_type} found with {property_name}='{search_value}'")
            return None
        elif len(values) > 1:
            logger.error(f"Multiple {entity_type} entities found with {property_name}='{search_value}' ({len(values)} results)")
            logger.error("Please ensure unique identifier is used")
            return None
        
        entity = values[0]
        entity_id = entity.get('id')
        entity_type_returned = entity.get('type')
        entity_name = entity.get('properties', {}).get('name', 'Unknown')
        
        logger.debug(f"Found {entity_type_returned}: '{entity_name}' (ID: {entity_id})")
        
        return {
            'entity_id': entity_id,
            'entity_type': entity_type_returned,
            'name': entity_name
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying Veza API: {e}")
        return None
```

### OAA enrichment - `oaa_enrichment_script.py`

Use this for OAA enrichment reference.
the idea is to leverage the OAA enrichment for other systems, the below uses OKTA but it could be anything, including hardcoded values. Examples:

1. Active Directory domain that needs a new attribute create by OAA enrichment that combines samAccountName and Description, the OAA enrichment should generate samaccountname+description value for the new attribute
2. use query to find existing attributes to combine them, sometimes there's no need to go externally to find the value.

#!/usr/bin/env python3
"""
List Okta OAuth/OIDC client apps and their Okta API scope grants.

- Auth modes:
  1) API token (SSWS)
  2) OAuth 2.0 (Client Credentials) for Okta APIs using a service app + private_key_jwt

Prints: appId, app label, allowed grants (scopeIds)

Docs:
- List Apps requires okta.apps.read scope (for OAuth) or SSWS token permissions.
- List App Grants requires okta.appGrants.read scope (for OAuth) or SSWS token permissions.
"""

from __future__ import annotations

import argparse
import jwt
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode, urlparse

import requests
from oaaclient.client import OAAClient, OAAResponseError

APP_ICON = """
"""

LINK_NEXT_RE = re.compile(r'<([^>]+)>\s*;\s*rel="next"')

# logging handler
logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


@dataclass
class OAuthPrivateKeyJWT:
    client_id: str
    private_key_pem: str
    kid: str
    token_url: str
    scopes: List[str]
    alg: str = "RS256"
    timeout_s: int = 30

    def mint_access_token(self) -> str:
        if jwt is None:
            raise RuntimeError(
                "Missing dependency: PyJWT. Install with: pip install pyjwt cryptography"
            )

        now = int(time.time())
        payload = {
            # Okta expects aud to be the org AS token endpoint:
            # https://{yourOktaDomain}/oauth2/v1/token
            "aud": self.token_url,
            "iss": self.client_id,
            "sub": self.client_id,
            "iat": now,
            "exp": now + 300,  # short-lived assertion
            "jti": str(uuid.uuid4()),
        }
        headers = {"kid": self.kid, "typ": "JWT", "alg": self.alg}
        assertion = jwt.encode(
            payload, self.private_key_pem, algorithm=self.alg, headers=headers
        )

        data = {
            "grant_type": "client_credentials",
            "scope": " ".join(self.scopes),
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        }

        resp = requests.post(
            self.token_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=data,
            timeout=self.timeout_s,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Token request failed: {resp.status_code} {resp.text}")

        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise RuntimeError(f"No access_token in response: {body}")
        return token


class OktaClient:
    def __init__(self, org_host: str, auth_header_value: str, timeout_s: int = 300):
        """_summary_

        Args:
            org_host (str): hostname for Okta Org (Example: acme.okta.com)
            auth_header_value (str): Authorization Header (SSWS XXXXXXX or Bearer XXXXXXX)
            timeout_s (int, optional): Request timeout to Okta. Defaults to 300.
        """

        self.org_host = f"https://{org_host}"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": auth_header_value,
            }
        )
        self.timeout_s = timeout_s

        log.debug("org_host: %s", self.org_host)
        log.debug("timeout_s: %s", self.timeout_s)

    def _request(
        self, method: str, url: str, *, retry_429: bool = True
    ) -> requests.Response:
        """
        Minimal 429 handling using X-Rate-Limit-Reset when present.
        """
        while True:
            resp = self.session.request(method, url, timeout=self.timeout_s)

            if resp.status_code != 429 or not retry_429:
                return resp

            reset = resp.headers.get("X-Rate-Limit-Reset")
            if reset and reset.isdigit():
                sleep_s = max(1, int(reset) - int(time.time()))
            else:
                sleep_s = 5

            log.warning(
                "Okta Rate Limit hit (HTTP 429) sleeping %s seconds then retrying %s",
                sleep_s,
                url,
            )
            time.sleep(sleep_s)

    def paged_get(self, first_url: str) -> Iterable[Dict]:
        """
        Iterate a paginated Okta collection endpoint that returns a JSON array.
        """
        url = first_url
        while url:
            resp = self._request("GET", url)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"GET failed: {resp.status_code} {resp.text} (url={url})"
                )

            items = resp.json()
            if not isinstance(items, list):
                raise RuntimeError(
                    f"Expected list response; got: {type(items)} (url={url})"
                )

            for it in items:
                yield it

            url = self.parse_next_link(resp.headers.get("Link"))

    def list_apps(self) -> Iterable[Dict]:
        params = {"limit": "200"}  # Max limit is 200

        url = f"{self.org_host}/api/v1/apps?{urlencode(params)}"
        return self.paged_get(url)

    def list_app_grants(self, app_id: str) -> List[str]:
        url = f"{self.org_host}/api/v1/apps/{app_id}/grants"

        resp = self._request("GET", url, retry_429=True)
        if resp.status_code == 404:
            # Some apps don't support grants endpoint; treat as no grants.
            return []
        if resp.status_code != 200:
            raise RuntimeError(
                f"GET grants failed for {app_id}: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError(
                f"Expected list of grants for {app_id}; got {type(data)}"
            )

        return sorted({grant.get("scopeId") for grant in data if grant.get("scopeId")})

    def parse_next_link(self, link_header: Optional[str]) -> Optional[str]:
        """
        Okta uses RFC5988 Link headers for pagination. We only need rel="next".
        """
        if not link_header:
            return None
        # Link: <https://.../api/v1/apps?after=...&limit=200>; rel="next"
        match = LINK_NEXT_RE.search(link_header)
        return match.group(1) if match else None


class OktaEnrichment:

    entity_type = "OktaApp"

    def __init__(self, okta_client: OktaClient, veza_client: OAAClient) -> None:
        self._okta_client = okta_client
        self._veza_client = veza_client
        self._application_scopes: dict = {}

    def process(self) -> None:
        self._get_okta_scopes()
        self._get_enriched_entities()
    
    def _get_okta_scopes(self):
        
        for app in self._okta_client.list_apps():
            app_id = str(app.get("id", ""))

            # Focus on OAuth clients these are the only ones supporting scope grants
            if app.get("signOnMode") != "OPENID_CONNECT":
                continue

            scopes = self._okta_client.list_app_grants(app_id)

            self._application_scopes[app_id] = { "scopes": scopes }


    def _get_enriched_entities(self) -> None:
        
        query = {
            "no_relation": False,
            "include_nodes": True,
            "query_type": "SOURCE_TO_DESTINATION",
            "source_node_types": {
                "nodes": [
                    {
                        "node_type": OktaEnrichment.entity_type,
                        "tags_to_get": [],
                        "direct_relationship_only": False
                    }
                ]
            },
            "node_relationship_type": "EFFECTIVE_ACCESS",
            "result_value_type": "SOURCE_NODES_WITH_COUNTS",
            "include_all_source_tags_in_results": False,
            "include_all_destination_tags_in_results": False,
            "include_sub_permissions": False,
            "include_permissions_summary": True
        }
        
        entities = self._veza_client.api_post(api_path="/api/v1/assessments/query_spec:nodes", data=query, params={"page_size": 10_000})
        
        for entity in entities:
            entity_id = entity.get("id")
            props = entity.get("properties", {}) or {}
            datasource_id = props.get("datasource_id")
            if entity_id in self._application_scopes and datasource_id:
                self._application_scopes[entity_id]["data_source_id"] = datasource_id
                self._application_scopes[entity_id]["exiting_granted_scopes"] = props.get("enrichmentprop_granted_scopes", [])

        
        for key, values in list(self._application_scopes.items()):
            if "data_source_id" not in values:
                log.warning("Removing %s: missing data_source_id", key)
                del self._application_scopes[key]
       
        for key, values in list(self._application_scopes.items()):  # make a copy first
            old_granted_scopes = values.get("exiting_granted_scopes")
            new_granted_scopes = values.get("scopes")

            if set(old_granted_scopes) == set(new_granted_scopes):
                log.debug("Ignoring %s: the before and after scopes are the same.", key)
                del self._application_scopes[key]
    
    def has_enriched_entities(self) -> bool:
        if self._application_scopes:
            return True
        
        return False

    def get_push_payload(self) -> dict:
        
        payload = {
            "enriched_entity_property_definitions": [
                {
                    "entity_type": OktaEnrichment.entity_type,
                    "enriched_properties": {
                        "granted_scopes": "STRING_LIST",
                    },
                },
            ],
            "enriched_entities": [
                {
                    "type": OktaEnrichment.entity_type,
                    "id": entity_id,
                    "data_source_id": values["data_source_id"],
                    "properties": {
                        "granted_scopes": values["scopes"],
                    },
                } for entity_id, values in self._application_scopes.items()
            ],
        }

        return payload

def run(org_host: str, auth_header_value: str, timeout_s: int, veza_host: str, veza_api_key: str, save_json: bool):

    # Create Okta Client
    okta = OktaClient(
        org_host=org_host, auth_header_value=auth_header_value, timeout_s=timeout_s
    )

    # Create Veza Client
    veza = OAAClient(url=veza_host, api_key=veza_api_key)

    # Instantiate Enrichment Class
    okta_enrichment = OktaEnrichment(okta_client=okta, veza_client=veza)
    okta_enrichment.process()
    
    if not okta_enrichment.has_enriched_entities():
        log.warning("No enriched_entities to push")
        return
    
    # Create Enrichtment Provider
    provider_name = f"Okta App Grants Enrichment {org_host}"
    data_source_name = provider_name
    
    provider = veza.get_provider(name=provider_name)

    if provider:
        provider_id = provider["id"]
        log.info("Found existing provider %s (id: %s)", provider_name, provider_id)
    else:
        
        provider = veza.create_provider(name=provider_name, custom_template="entity_enrichment")
        provider_id = provider["id"]
        
        if APP_ICON:
            veza.update_provider_icon(provider_id=provider_id, base64_icon=APP_ICON)
        log.info("Created new provider %s (id: %s)", provider_name, provider_id)
    
    # Push Enrichment Data
    
    try:
        veza.push_metadata(provider_name=provider_name, data_source_name=data_source_name, metadata=okta_enrichment.get_push_payload(), save_json=save_json)
        
    except OAAResponseError as error:
        log.error("%s: %s (%s)", error.error, error.message, error.status_code)
        log.error(error.details)
        if hasattr(error, "details"):
            for detail in error.details:
                log.error(detail)
        raise error


def main():
    p = argparse.ArgumentParser(
        description="List Okta OAuth apps and their scope grants."
    )
    # Required Arguments
    p.add_argument(
        "--okta-org",
        required=True,
        help="Okta org hostname, e.g. acme.okta.com",
    )
    p.add_argument(
        "--okta-auth",
        required=True,
        choices=["token", "oauth2"],
        help="Authentication mode: token (SSWS) or oauth2 (service app private_key_jwt).",
    )
    p.add_argument(
        "--veza-host",
        required=True,
        help="Veza host to push data to."
    )

    # oauth2 mode (service app)
    p.add_argument(
        "--client-id", help="OAuth service app client id (required for oauth2 mode)."
    )
    p.add_argument(
        "--private-key-pem",
        help="Path to private key PEM used to sign the client assertion (required for oauth2 mode).",
    )
    p.add_argument(
        "--kid", help="Key ID (kid) matching the public key in the service app's JWKS."
    )
    p.add_argument(
        "--jwt-alg",
        default="RS256",
        help="JWT signing algorithm (default RS256). Must match your key type.",
    )

    # Optinoal
    p.add_argument(
        "--save-json",
        action="store_true",
        help="Save the OAA JSON payload to a file before pushing it."
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Set logging level to debug"
    )

    args = p.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("debug logging level enabled.")

    log.debug("args: %s", args)
    
    org_url = args.okta_org.strip().lower()
    if "://" not in org_url:
        org_url = f"https://{org_url}"

    org_url = urlparse(org_url).netloc

    timeout_s = 30

    if args.okta_auth == "token":
        # token mode
        token = os.environ.get("OKTA_API_TOKEN")
        if not token:
            log.error("Missing API Token from OKTA_API_TOKEN environment variable")
            sys.exit(2)
        auth_header = f"SSWS {token}"

    else:
        # oauth2 mode
        missing = [
            x
            for x in ["client_id", "private_key_pem", "kid"]
            if getattr(args, x) is None
        ]
        if missing:
            log.error(
                "Missing required args for oauth2 mode: %s",
                ", ".join("--" + m.replace("_", "-") for m in missing),
            )
            sys.exit(2)

        with open(args.private_key_pem, "r", encoding="utf-8") as file:
            private_key_pem = file.read()

        token_url = (
            f"https://{org_url}/oauth2/v1/token"  # org authorization server token endpoint
        )
        requested_scopes = ["okta.apps.read", "okta.appGrants.read"]
        mint = OAuthPrivateKeyJWT(
            client_id=args.client_id,
            private_key_pem=private_key_pem,
            kid=args.kid,
            token_url=token_url,
            scopes=requested_scopes,
            alg=args.jwt_alg,
            timeout_s=timeout_s,
        )
        access_token = mint.mint_access_token()

        granted_scopes = jwt.decode(
            access_token, options={"verify_signature": False}
        ).get("scp", [])

        missing_scopes = [
            scope for scope in requested_scopes if scope not in granted_scopes
        ]

        if missing_scopes:
            log.error("Okta Access Token missing scopes: %s", ", ".join(missing_scopes))
            sys.exit(2)

        auth_header = f"Bearer {access_token}"

    
    veza_api_key = os.getenv("VEZA_API_KEY")

    if not veza_api_key:
        log.error("Missing VEZA_API_KEY environment variable.")
        sys.exit(2)
    
    run(org_host=org_url, auth_header_value=auth_header, timeout_s=timeout_s, veza_host=args.veza_host, veza_api_key=veza_api_key, save_json=args.save_json)


if __name__ == "__main__":
    main()
    log.info("Completed OAA Enrichment Push")


---

## OAA Enrichment — Findings & Constraints (Lab-Tested April 2026)

### Entity Enrichment Template — Supported Entity Types

The `entity_enrichment` template **only supports native/built-in Veza entity types**. It does NOT support OAA custom entity types (dot-notation types like `OAA.<Provider>.<EntityType>`).

**Works (HTTP 200):**
- `AzureADUser`
- `OktaUser`
- `OktaApp`
- `AwsIamRole`
- `CustomApplication`
- Any other native Veza graph entity type

**Does NOT work (HTTP 500):**
- `OAA.GICO.User`
- `OAA.<AnyProvider>.User`
- Any OAA custom entity sub-type with dot notation (`OAALocalUser`, `CustomApplicationLocalUser`, `local_user`, etc.)

This is a **Veza platform limitation**, not a script bug. The enrichment push returns HTTP 200 with no warnings for native types but consistently returns HTTP 500 for all OAA custom entity type variants.

### Enrichment Provider Architecture

- An enrichment provider uses `custom_template="entity_enrichment"` and is **separate** from the application provider it enriches.
- You cannot push enrichment payloads (`enriched_entity_property_definitions`) to a provider created with `custom_application` template — this returns HTTP 400.
- Create/get pattern:
  ```python
  provider = veza.get_provider(name=provider_name)
  if not provider:
      provider = veza.create_provider(name=provider_name, custom_template="entity_enrichment")
  ```

### Enrichment Payload Structure

```json
{
  "enriched_entity_property_definitions": [
    {
      "entity_type": "AzureADUser",
      "enriched_properties": {
        "new_email": "STRING"
      }
    }
  ],
  "enriched_entities": [
    {
      "type": "AzureADUser",
      "id": "<graph-entity-uuid>",
      "data_source_id": "<datasource-uuid-from-entity-properties>",
      "properties": {
        "new_email": "value"
      }
    }
  ]
}
```

**Key fields:**
- `id` — The graph entity UUID (from query results `entity.get("id")`)
- `data_source_id` — The datasource UUID from `entity.get("properties", {}).get("datasource_id")` — this is the **original** data source of the entity being enriched, NOT the enrichment provider's data source
- Supported property types: `STRING`, `STRING_LIST`, `BOOLEAN`, `NUMBER`, `TIMESTAMP`

### Enrichment Property Naming

Once pushed and extracted, enriched properties appear on entities with the prefix `enrichmentprop_`. For example:
- Pushed as `granted_scopes` → visible as `enrichmentprop_granted_scopes`
- Pushed as `new_email` → visible as `enrichmentprop_new_email`

### Graph Extraction Timing

After a successful push (HTTP 200), the enrichment data source status will be `EXTRACTION_PENDING`. The enriched properties will **not** appear on entities immediately — they require a graph extraction cycle to complete. This can take seconds to minutes depending on tenant load.

### Querying Entities for Enrichment

When querying entities to enrich, use the assessment query API:
- Endpoint: `POST /api/v1/assessments/query_spec:nodes?page_size=10000`
- The `node_type` in the query must match the entity type you plan to enrich
- Each returned entity provides `id` (graph UUID) and `properties.datasource_id` — both are required for the enrichment payload

### Workaround for OAA Custom Entity Types

Since enrichment doesn't work for OAA custom entity types (`OAA.X.Y`), alternatives:
1. Add the property directly in the OAA custom application connector that creates the entity (push it as a custom property on the `local_user`, `local_group`, etc.)
2. File a support request with Veza to add OAA custom entity type support to the enrichment template
