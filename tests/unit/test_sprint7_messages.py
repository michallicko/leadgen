"""Unit tests for Sprint 7 message management UX features.

BL-177: Batch message review (bulk approve/reject)
BL-181: A/B variant support (variant_group, variant_angle fields)
BL-182: Keyboard shortcuts (frontend-only, no backend tests needed)
"""
from tests.conftest import auth_header


def _setup_campaign_with_messages(db, seed, status="review", msg_count=3, variants=1):
    """Create a campaign with draft messages.

    Args:
        variants: Number of variants per message (1=A only, 2=A+B, 3=A+B+C).
    """
    import uuid
    from api.models import Campaign, CampaignContact, Message

    tenant_id = seed["tenant"].id
    owner = seed["owners"][0]

    campaign = Campaign(
        tenant_id=tenant_id,
        name="Sprint 7 Test Campaign",
        status=status,
    )
    db.session.add(campaign)
    db.session.flush()

    messages = []
    campaign_contacts = []
    variant_letters = ["a", "b", "c"]
    angle_keys = [None, "pain", "opportunity"]

    for i in range(min(msg_count, len(seed["contacts"]))):
        contact = seed["contacts"][i]
        cc = CampaignContact(
            campaign_id=campaign.id,
            contact_id=contact.id,
            tenant_id=tenant_id,
            status="generated",
        )
        db.session.add(cc)
        db.session.flush()
        campaign_contacts.append(cc)

        vg_id = str(uuid.uuid4()) if variants > 1 else None

        for v in range(variants):
            m = Message(
                tenant_id=tenant_id,
                contact_id=contact.id,
                owner_id=owner.id,
                channel="linkedin_connect",
                sequence_step=1,
                variant=variant_letters[v],
                label="Step 1",
                subject=f"Subject for {contact.first_name} v{variant_letters[v].upper()}",
                body=f"Hello {contact.first_name}, variant {variant_letters[v].upper()} message.",
                status="draft",
                campaign_contact_id=cc.id,
                tag_id=seed["tags"][0].id,
                variant_group=vg_id,
                variant_angle=angle_keys[v],
            )
            db.session.add(m)
            messages.append(m)

    db.session.flush()
    db.session.commit()
    return campaign, campaign_contacts, messages


class TestBatchReject:
    """BL-177: Batch reject via PATCH /api/messages/batch."""

    def test_batch_reject_updates_status(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=3)

        ids = [str(m.id) for m in msgs]

        resp = client.patch("/api/messages/batch", headers=headers, json={
            "ids": ids,
            "fields": {"status": "rejected", "review_notes": "Bulk rejected"},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["updated"] == 3

        # Verify all messages are rejected
        for msg_id in ids:
            row = db.session.execute(
                db.text("SELECT status, review_notes FROM messages WHERE id = :id"),
                {"id": msg_id},
            ).fetchone()
            assert row[0] == "rejected"
            assert row[1] == "Bulk rejected"

    def test_batch_update_empty_ids_rejected(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"

        resp = client.patch("/api/messages/batch", headers=headers, json={
            "ids": [],
            "fields": {"status": "approved"},
        })
        assert resp.status_code == 400

    def test_batch_approve_sets_approved_at(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(db, seed, msg_count=2)

        ids = [str(m.id) for m in msgs]

        resp = client.patch("/api/messages/batch", headers=headers, json={
            "ids": ids,
            "fields": {"status": "approved", "approved_at": "2026-03-01T12:00:00Z"},
        })
        assert resp.status_code == 200
        assert resp.get_json()["updated"] == 2

        # Verify approved_at is set
        for msg_id in ids:
            row = db.session.execute(
                db.text("SELECT status, approved_at FROM messages WHERE id = :id"),
                {"id": msg_id},
            ).fetchone()
            assert row[0] == "approved"
            assert row[1] is not None


class TestVariantFields:
    """BL-181: variant_group and variant_angle fields in messages."""

    def test_list_messages_includes_variant_fields(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(
            db, seed, msg_count=1, variants=2
        )

        resp = client.get("/api/messages?status=draft", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        messages = data["messages"]

        # Should have 2 messages (A and B variants)
        assert len(messages) >= 2

        # Find our variant messages
        our_msgs = [m for m in messages if m["variant_group"] is not None]
        assert len(our_msgs) == 2

        # Check variant_group is the same UUID
        assert our_msgs[0]["variant_group"] == our_msgs[1]["variant_group"]

        # Check variant_angle
        angles = {m["variant"] for m in our_msgs}
        assert "A" in angles
        assert "B" in angles

        # A has no angle, B has 'pain' angle
        a_msg = next(m for m in our_msgs if m["variant"] == "A")
        b_msg = next(m for m in our_msgs if m["variant"] == "B")
        assert a_msg["variant_angle"] is None
        assert b_msg["variant_angle"] == "pain"

    def test_three_variants_all_returned(self, client, seed_companies_contacts, db):
        headers = auth_header(client)
        headers["X-Namespace"] = "test-corp"
        seed = seed_companies_contacts
        campaign, ccs, msgs = _setup_campaign_with_messages(
            db, seed, msg_count=1, variants=3
        )

        resp = client.get("/api/messages?status=draft", headers=headers)
        assert resp.status_code == 200
        messages = resp.get_json()["messages"]

        our_msgs = [m for m in messages if m["variant_group"] is not None]
        assert len(our_msgs) == 3

        variants = sorted(m["variant"] for m in our_msgs)
        assert variants == ["A", "B", "C"]


class TestVariantAngles:
    """BL-181: Verify VARIANT_ANGLES constant is well-formed."""

    def test_variant_angles_structure(self):
        from api.services.message_generator import VARIANT_ANGLES, VARIANT_LETTERS

        assert len(VARIANT_ANGLES) >= 2
        for angle in VARIANT_ANGLES:
            assert "key" in angle
            assert "label" in angle
            assert "instruction" in angle
            assert len(angle["instruction"]) > 10

        assert VARIANT_LETTERS == ["A", "B", "C"]

    def test_estimate_generation_cost_with_variants(self):
        from api.services.message_generator import estimate_generation_cost

        template_config = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
            {"step": 2, "channel": "linkedin_connect", "label": "LI", "enabled": True},
        ]

        # Single variant
        est1 = estimate_generation_cost(template_config, 10, variant_count=1)
        assert est1["total_messages"] == 20  # 2 steps * 10 contacts * 1 variant
        assert est1["variant_count"] == 1

        # Two variants
        est2 = estimate_generation_cost(template_config, 10, variant_count=2)
        assert est2["total_messages"] == 40  # 2 steps * 10 contacts * 2 variants
        assert est2["variant_count"] == 2

        # Three variants
        est3 = estimate_generation_cost(template_config, 10, variant_count=3)
        assert est3["total_messages"] == 60
        assert est3["variant_count"] == 3

        # Cost should scale linearly with variant count
        assert est2["total_cost"] > est1["total_cost"]
        assert est3["total_cost"] > est2["total_cost"]

    def test_estimate_clamps_variant_count(self):
        from api.services.message_generator import estimate_generation_cost

        template_config = [
            {"step": 1, "channel": "email", "label": "Email 1", "enabled": True},
        ]

        # 0 should be clamped to 1
        est0 = estimate_generation_cost(template_config, 5, variant_count=0)
        assert est0["variant_count"] == 1

        # 5 should be clamped to 3
        est5 = estimate_generation_cost(template_config, 5, variant_count=5)
        assert est5["variant_count"] == 3
