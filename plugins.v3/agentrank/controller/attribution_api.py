"""播放同步、订阅归因与榜单消费记录。"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from .errors import ApiContractError
from ..service.feedback_proposal import FeedbackProposalService
from ..service.feedback_queue import FeedbackQueueError
from ..service.prompt import effective_persona_prompt


class AttributionApiMixin:
    """播放同步、订阅归因与榜单消费记录。"""

    async def playback_sync(self, payload: Any, actor_id: str = "") -> Dict[str, Any]:
        """立即同步指定用户播放画像并返回数据源状态。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        service = getattr(self.plugin, "_playback_service", None)
        if service is None:
            raise ApiContractError(503, "playback_unavailable", "播放画像服务尚未就绪")
        try:
            snapshot = await asyncio.to_thread(service.collect, target, self.plugin._config)
        except Exception as error:
            raise ApiContractError(502, "playback_sync_failed", "播放画像同步失败") from error
        calibration_event = None
        calibration_created = False
        try:
            calibration_event, calibration_created = FeedbackProposalService(
                self._repository(),
                record_limit=int(
                    self.plugin._config.get("analysis_record_limit") or 500
                ),
                persona_prompt=effective_persona_prompt(
                    self.plugin._config.get("persona_preset"),
                    self.plugin._config.get("persona_prompt"),
                ),
                interaction_mode=str(
                    self.plugin._config.get("interaction_mode") or "auto"
                ),
            ).create_playback_calibration(
                target,
                snapshot,
                actor_id=actor_id,
            )
        except Exception:
            calibration_event = None
            calibration_created = False
        if calibration_event is not None and calibration_created:
            try:
                self._feedback_queue().enqueue_event(calibration_event)
            except Exception:
                calibration_created = False
        data = snapshot.to_dict()
        data["calibration_created"] = calibration_created
        data["calibration_event_id"] = (
            calibration_event.event_id if calibration_event is not None else ""
        )
        data["calibration_question_id"] = ""
        data["learning_health"] = self._repository().build_learning_health(target).to_dict()
        return self._success(data)

    def start_pending_interview(
        self, payload: Any, actor_id: str = ""
    ) -> Dict[str, Any]:
        """启动由反馈 Agent 逐题生成的待办中心问询验收。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        request_key = str(body.get("idempotency_key") or "").strip()
        if not request_key or len(request_key) > 256:
            raise ApiContractError(
                422, "idempotency_key_invalid", "问询验收缺少有效幂等标识"
            )
        try:
            total = int(body.get("total") or 10)
        except (TypeError, ValueError) as error:
            raise ApiContractError(
                422, "interview_total_invalid", "问询题数必须是整数"
            ) from error
        if not 1 <= total <= 10:
            raise ApiContractError(
                422, "interview_total_invalid", "问询题数必须介于 1 到 10"
            )
        snapshot = self._repository().load_playback_snapshot(target)
        if snapshot is None:
            raise ApiContractError(
                409, "playback_unavailable", "当前没有可用于动态问询的播放画像"
            )
        event, created = FeedbackProposalService(
            self._repository(),
            record_limit=int(
                self.plugin._config.get("analysis_record_limit") or 500
            ),
            persona_prompt=effective_persona_prompt(
                self.plugin._config.get("persona_preset"),
                self.plugin._config.get("persona_prompt"),
            ),
            interaction_mode=str(
                self.plugin._config.get("interaction_mode") or "auto"
            ),
        ).create_pending_interview(
            target,
            snapshot,
            self._repository().load_board(target),
            actor_id=actor_id,
            idempotency_key=request_key,
            total=total,
        )
        if event is None:
            raise ApiContractError(
                409,
                "pending_question_exists",
                "请先回答或关闭当前待办问题，再启动问询验收",
            )
        try:
            job = self._feedback_queue().enqueue_event(event)
        except FeedbackQueueError as error:
            raise ApiContractError(
                503,
                "feedback_queue_failed",
                "问询事件已保存，但 Agent 任务入队失败；可使用原请求重试",
            ) from error
        return self._success(
            {
                "profile_id": target,
                "event_id": event.event_id,
                "created": created,
                "total": total,
                "queue_status": job.status,
                "memory_delta": {},
            }
        )

    def subscribe(self, payload: Any) -> Dict[str, Any]:
        """通过运行时安全链创建单项手动订阅。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        self._require_enabled()
        candidate_id = self._candidate_id(body)
        runtime = getattr(self.plugin, "_runtime", None)
        service = getattr(runtime, "subscription_service", None) if runtime else None
        if service is None:
            raise ApiContractError(409, "subscription_not_ready", "手动订阅安全链尚未就绪")
        result = service.subscribe(
            target,
            candidate_id,
            float(self.plugin._config.get("confidence_threshold") or 0.0),
        )
        if not result.success:
            raise ApiContractError(409, result.code, result.message)
        short_term = None
        board = self._repository().load_board(target)
        if board is not None and any(
            item.candidate_id == candidate_id for item in board.recommendations
        ):
            observed_at = datetime.now(timezone.utc).isoformat()
            try:
                self._repository().record_board_interaction(
                    target,
                    board.run_id,
                    board.revision,
                    "subscribe",
                    observed_at,
                )
                short_term = self._append_short_term_signal(
                    profile_id=target,
                    kind="subscribe",
                    idempotency_key=(
                        str(body.get("idempotency_key") or "").strip()
                        or f"subscribe:{board.run_id}:{board.revision}:{candidate_id}"
                    ),
                    candidate_id=candidate_id,
                    run_id=board.run_id,
                    board_revision=board.revision,
                    source="moviepilot_subscription",
                    strength=0.8,
                    decay_days=90,
                )
            except Exception as error:
                short_term = {
                    "created": False,
                    "error": "short_term_signal_failed",
                    "message": str(error)[:160],
                }
        data = dict(result.__dict__)
        data["short_term"] = short_term
        return self._success(data)

    def attribution(self, profile_id: Any) -> Dict[str, Any]:
        """返回指定 profile 的安全结果归因记录。"""
        target = self._profile_id(profile_id)
        try:
            records = self._attribution_service().public_records(target)
        except ApiContractError:
            raise
        except Exception as error:
            raise ApiContractError(
                500, "attribution_read_failed", "结果归因读取失败"
            ) from error
        return self._success({"profile_id": target, "records": records})

    def record_native_drawer_opened(self, payload: Any) -> Dict[str, Any]:
        """仅记录原生订阅抽屉已打开，不把返回值解释为订阅成功。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        candidate_id = self._candidate_id(body)
        try:
            record = self._attribution_service().record_native_drawer_opened(
                target, candidate_id
            )
        except ApiContractError:
            raise
        except ValueError as error:
            raise ApiContractError(
                409,
                "attribution_candidate_unavailable",
                "当前推荐已变化，请刷新榜单后重试",
            ) from error
        except Exception as error:
            raise ApiContractError(
                500, "attribution_record_failed", "原生订阅交互记录失败"
            ) from error
        return self._success(record.to_public_dict())

    def verify_attribution(self, payload: Any) -> Dict[str, Any]:
        """立即复查指定 profile 的订阅、入库和播放事实。"""
        body = self._payload(payload)
        target = self._profile_id(body.get("profile_id"))
        try:
            result = self._attribution_service().verify_profile(target)
        except ApiContractError:
            raise
        except Exception as error:
            raise ApiContractError(
                500,
                "attribution_verification_failed",
                "结果归因暂时无法复查，已保留上次可信状态",
            ) from error
        return self._success(result.to_dict())

    def learning_health(self, profile_id: Any) -> Dict[str, Any]:
        """返回当前 profile 的短期学习、确认记忆和归因覆盖摘要。"""
        target = self._profile_id(profile_id)
        return self._success(self._repository().build_learning_health(target).to_dict())

    def record_exposure(self, payload: Any) -> Dict[str, Any]:
        """记录当前榜单实际进入页面可见区的一次曝光。"""
        body = self._payload(payload)
        target, board, revision = self._board_context(body)
        raw_ids = body.get("candidate_ids")
        if raw_ids is None:
            candidate_ids = [item.candidate_id for item in board.recommendations]
        elif isinstance(raw_ids, (list, tuple, set)):
            candidate_ids = [str(item or "").strip() for item in raw_ids]
        else:
            candidate_ids = None
        if candidate_ids is None or any(not item for item in candidate_ids):
            raise ApiContractError(422, "candidate_ids_invalid", "candidate_ids 必须是候选标识数组")
        allowed = {item.candidate_id for item in board.recommendations}
        if any(item not in allowed for item in candidate_ids):
            raise ApiContractError(409, "candidate_not_on_board", "曝光候选不属于当前榜单")
        try:
            consumption = self._repository().record_board_exposure(
                target,
                board.run_id,
                revision,
                candidate_ids,
                datetime.now(timezone.utc).isoformat(),
            )
            health = self._repository().build_learning_health(target)
        except Exception as error:
            raise ApiContractError(500, "exposure_record_failed", "榜单曝光记录失败") from error
        return self._success(
            {
                "consumption": consumption.to_dict(),
                "learning_health": health.to_dict(),
            }
        )

    def record_detail_opened(self, payload: Any) -> Dict[str, Any]:
        """记录当前榜单候选详情被用户打开，并生成中等强度短期信号。"""
        body = self._payload(payload)
        candidate_id = self._candidate_id(body)
        target, board, revision = self._board_context(body, candidate_id=candidate_id)
        observed_at = datetime.now(timezone.utc).isoformat()
        try:
            consumption = self._repository().record_board_detail_opened(
                target,
                board.run_id,
                revision,
                candidate_id,
                observed_at,
            )
            signal = self._append_short_term_signal(
                profile_id=target,
                kind="detail_opened",
                idempotency_key=f"detail:{board.run_id}:{revision}:{candidate_id}",
                candidate_id=candidate_id,
                run_id=board.run_id,
                board_revision=revision,
                source="agentrank_detail",
                strength=0.3,
                decay_days=30,
            )
        except Exception as error:
            raise ApiContractError(500, "detail_record_failed", "详情打开记录失败") from error
        return self._success(
            {"consumption": consumption.to_dict(), "short_term": signal}
        )

    def record_consumption_interaction(self, payload: Any) -> Dict[str, Any]:
        """记录订阅或播放结果等榜单消费状态，并写入对应短期信号。"""
        body = self._payload(payload)
        candidate_id = self._candidate_id(body)
        kind = str(body.get("kind") or "").strip().casefold()
        signal_config = {
            "subscribe": (0.8, 90, "moviepilot_subscription"),
            "playback_start": (0.45, 30, "playback_reporting"),
            "playback_completed": (0.95, 90, "playback_reporting"),
            "playback_abandoned": (-0.35, 30, "playback_reporting"),
        }
        if kind not in signal_config:
            raise ApiContractError(422, "invalid_consumption_kind", "不支持的榜单消费状态")
        target, board, revision = self._board_context(body, candidate_id=candidate_id)
        observed_at = datetime.now(timezone.utc).isoformat()
        strength, decay_days, source = signal_config[kind]
        idempotency_key = (
            str(body.get("idempotency_key") or "").strip()
            or f"consumption:{kind}:{board.run_id}:{revision}:{candidate_id}"
        )
        try:
            consumption = self._repository().record_board_interaction(
                target, board.run_id, revision, kind, observed_at
            )
            signal = self._append_short_term_signal(
                profile_id=target,
                kind=kind,
                idempotency_key=idempotency_key,
                candidate_id=candidate_id,
                run_id=board.run_id,
                board_revision=revision,
                source=source,
                strength=strength,
                decay_days=decay_days,
            )
        except Exception as error:
            raise ApiContractError(500, "consumption_record_failed", "榜单消费状态记录失败") from error
        return self._success(
            {"consumption": consumption.to_dict(), "short_term": signal}
        )
