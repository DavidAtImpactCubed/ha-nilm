from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
import tensorflow as tf


def _infer_output_indices(head: tf.keras.Model) -> Tuple[Optional[int], int]:
    out_names = [getattr(o, "name", "").lower() for o in head.outputs]

    cls_idx = next(
        (i for i, n in enumerate(out_names) if ("on" in n or "class" in n or "sigmoid" in n)),
        None,
    )
    reg_idx = next(
        (i for i, n in enumerate(out_names) if ("reg" in n or "power" in n or "mse" in n)),
        None,
    )

    if cls_idx is None:
        if len(head.outputs) == 1:
            cls_idx = 0
        elif len(head.outputs) >= 2:
            cls_idx = 1
        else:
            raise RuntimeError("Head model has no outputs.")

    if len(head.outputs) == 1:
        reg_idx = None
    elif reg_idx is None:
        reg_idx = 0 if cls_idx != 0 else (1 if len(head.outputs) > 1 else None)

    return reg_idx, int(cls_idx)


def _to_probability(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if x.size == 0:
        return x
    if float(np.min(x)) < -0.05 or float(np.max(x)) > 1.05:
        x = 1.0 / (1.0 + np.exp(-x))
    return np.clip(x, 0.0, 1.0)


def _normalize_power_targets(targets_power: list[float], settings: Dict[str, Any]) -> np.ndarray:
    power_mean = float(settings["power_mean"])
    power_std = float(settings["power_std"])
    if abs(power_std) < 1e-12:
        raise ValueError("settings.power_std must be non-zero.")
    y_power = np.asarray(targets_power, dtype=np.float32).reshape(-1)
    return ((y_power - power_mean) / power_std).astype(np.float32)


def _denorm_power(v_norm: np.ndarray, settings: Dict[str, Any]) -> np.ndarray:
    power_mean = float(settings["power_mean"])
    power_std = float(settings["power_std"])
    return v_norm.astype(np.float32) * power_std + power_mean


def _best_prob_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> Tuple[float, float]:
    y_true = np.asarray(y_true, dtype=np.int32).reshape(-1)
    y_prob = _to_probability(y_prob)

    if y_true.size == 0 or np.unique(y_true).size < 2:
        return 0.5, 0.0

    best_thr = 0.5
    best_f1 = -1.0
    for thr in np.linspace(0.05, 0.95, 19):
        y_pred = (y_prob >= thr).astype(np.int32)
        f1 = _binary_f1_score(y_true, y_pred)
        if f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)
    return best_thr, best_f1


def _binary_f1_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=np.int32).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=np.int32).reshape(-1)
    if y_true.size == 0 or y_pred.size == 0 or y_true.size != y_pred.size:
        return 0.0

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    denom = (2 * tp) + fp + fn
    if denom <= 0:
        return 0.0
    return float((2.0 * tp) / float(denom))


def _best_power_threshold(y_true_w: np.ndarray, y_pred_w: np.ndarray, gt_on_threshold: float = 5.0) -> Tuple[float, float]:
    eps = 1e-12
    y_true_w = np.clip(np.asarray(y_true_w, dtype=np.float32).reshape(-1), 0.0, None)
    y_pred_w = np.clip(np.asarray(y_pred_w, dtype=np.float32).reshape(-1), 0.0, None)

    true_on = y_true_w >= float(gt_on_threshold)
    if int(true_on.sum()) == 0:
        fallback = float(max(gt_on_threshold, float(np.max(y_pred_w)) + 1.0 if y_pred_w.size else gt_on_threshold))
        return fallback, 0.0

    cand = np.unique(np.quantile(y_pred_w, np.linspace(0.0, 1.0, 101)))
    cand = cand[cand >= float(gt_on_threshold)]
    if cand.size == 0:
        cand = np.array([float(gt_on_threshold)], dtype=np.float32)
    elif not np.any(np.isclose(cand, float(gt_on_threshold))):
        cand = np.unique(np.append(cand, float(gt_on_threshold)))

    best_t = float(cand[0])
    best_f1 = -1.0
    for t in cand:
        pred_on = y_pred_w >= float(t)
        tp = np.sum(pred_on & true_on)
        fp = np.sum(pred_on & ~true_on)
        fn = np.sum(~pred_on & true_on)
        f1 = float((2.0 * tp) / (2.0 * tp + fp + fn + eps))
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)

    return best_t, best_f1


def train_ref_embedding(
    *,
    query_embeddings: list[list[float]],
    targets_on: list[int],
    targets_power: Optional[list[float]],
    settings: Dict[str, Any],
    head_model_path: str,
    epochs: int = 200,
    lr: float = 0.01,
    batch_size: int = 1024,
    seed: int = 0,
    patience: int = 5,
    min_delta: float = 1e-4,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    progress_every_s: float = 1.0,
) -> Tuple[list[float], Dict[str, Any], Dict[str, float]]:
    tf.random.set_seed(seed)
    np.random.seed(seed)

    Q = tf.convert_to_tensor(query_embeddings, dtype=tf.float32)
    y_on = tf.convert_to_tensor(targets_on, dtype=tf.float32)

    y_power_norm_np: Optional[np.ndarray] = None
    if targets_power is not None:
        if len(targets_power) != len(targets_on):
            raise ValueError("targets_power and targets_on must have the same length.")
        y_power_norm_np = _normalize_power_targets(targets_power, settings)
        y_power = tf.convert_to_tensor(y_power_norm_np, dtype=tf.float32)
        fine_tune_target = "power"
    else:
        y_power = None
        fine_tune_target = "onoff"

    N = int(Q.shape[0])
    D = int(Q.shape[1])

    head = tf.keras.models.load_model(head_model_path, compile=False)
    head.trainable = False
    if len(head.inputs) != 2:
        raise RuntimeError("Expected head with 2 inputs (ref, query).")

    reg_idx, onoff_idx = _infer_output_indices(head)
    if fine_tune_target == "power" and reg_idx is None:
        raise RuntimeError("Head model does not expose a regression output for power fine-tuning.")

    ref_emb = tf.Variable(tf.random.normal((1, D), stddev=0.05), trainable=True, name="ref_embedding")
    optimizer = tf.keras.optimizers.Adam(learning_rate=lr)
    bce_loss_fn = tf.keras.losses.BinaryCrossentropy(from_logits=False)
    mse_loss_fn = tf.keras.losses.MeanSquaredError()

    if y_power is not None:
        ds = tf.data.Dataset.from_tensor_slices((Q, y_on, y_power))
    else:
        ds = tf.data.Dataset.from_tensor_slices((Q, y_on))
    ds = ds.shuffle(min(10_000, N), seed=seed, reshuffle_each_iteration=True)
    ds = ds.batch(batch_size, drop_remainder=False).prefetch(tf.data.AUTOTUNE)

    steps_per_epoch = int((N + batch_size - 1) // batch_size)

    @tf.function
    def train_step_onoff(q_batch, y_on_batch):
        with tf.GradientTape() as tape:
            bsz = tf.shape(q_batch)[0]
            ref_batch = tf.broadcast_to(ref_emb, (bsz, D))
            outputs = head([ref_batch, q_batch], training=False)
            pred_on = tf.reshape(outputs[onoff_idx], (-1,))
            cls_loss = bce_loss_fn(y_on_batch, pred_on)
        grads = tape.gradient(cls_loss, [ref_emb])
        optimizer.apply_gradients(zip(grads, [ref_emb]))
        return cls_loss, cls_loss, tf.constant(0.0, dtype=tf.float32)

    @tf.function
    def train_step_power(q_batch, y_on_batch, y_power_batch):
        with tf.GradientTape() as tape:
            bsz = tf.shape(q_batch)[0]
            ref_batch = tf.broadcast_to(ref_emb, (bsz, D))
            outputs = head([ref_batch, q_batch], training=False)
            pred_reg = tf.reshape(outputs[reg_idx], (-1,))
            pred_on = tf.reshape(outputs[onoff_idx], (-1,))
            reg_loss = mse_loss_fn(y_power_batch, pred_reg)
            cls_loss = bce_loss_fn(y_on_batch, pred_on)
            total_loss = reg_loss + cls_loss
        grads = tape.gradient(total_loss, [ref_emb])
        optimizer.apply_gradients(zip(grads, [ref_emb]))
        return total_loss, cls_loss, reg_loss

    total_losses: list[float] = []
    cls_losses: list[float] = []
    reg_losses: list[float] = []
    best_total = float("inf")
    best_epoch = -1
    best_ref_emb = None
    last_emit = 0.0

    for epoch in range(epochs):
        total_sum = 0.0
        cls_sum = 0.0
        reg_sum = 0.0
        step = 0

        for batch in ds:
            step += 1
            if y_power is None:
                q_batch, y_on_batch = batch
                total_t, cls_t, reg_t = train_step_onoff(q_batch, y_on_batch)
            else:
                q_batch, y_on_batch, y_power_batch = batch
                total_t, cls_t, reg_t = train_step_power(q_batch, y_on_batch, y_power_batch)

            total_v = float(total_t.numpy())
            cls_v = float(cls_t.numpy())
            reg_v = float(reg_t.numpy())
            total_sum += total_v
            cls_sum += cls_v
            reg_sum += reg_v

            if on_progress:
                now = time.monotonic()
                if (now - last_emit) >= progress_every_s:
                    last_emit = now
                    avg_total = total_sum / max(1, step)
                    avg_cls = cls_sum / max(1, step)
                    avg_reg = reg_sum / max(1, step)
                    on_progress(
                        {
                            "phase": "running",
                            "epoch": epoch + 1,
                            "total_epochs": epochs,
                            "step": step,
                            "total_steps": steps_per_epoch,
                            "pct": (step / max(1, steps_per_epoch)) * 100.0,
                            "loss": avg_total,
                            "min_loss": float(min(total_losses) if total_losses else avg_total),
                            "cls_loss": avg_cls,
                            "reg_loss": avg_reg if y_power is not None else None,
                            "fine_tune_target": fine_tune_target,
                        }
                    )

        epoch_total = total_sum / max(1, step)
        epoch_cls = cls_sum / max(1, step)
        epoch_reg = reg_sum / max(1, step)
        total_losses.append(float(epoch_total))
        cls_losses.append(float(epoch_cls))
        reg_losses.append(float(epoch_reg))

        if on_progress:
            on_progress(
                {
                    "phase": "running",
                    "epoch": epoch + 1,
                    "total_epochs": epochs,
                    "step": steps_per_epoch,
                    "total_steps": steps_per_epoch,
                    "pct": 100.0,
                    "loss": float(epoch_total),
                    "min_loss": float(min(total_losses)),
                    "cls_loss": float(epoch_cls),
                    "reg_loss": float(epoch_reg) if y_power is not None else None,
                    "fine_tune_target": fine_tune_target,
                }
            )

        if epoch_total + min_delta < best_total:
            best_total = epoch_total
            best_epoch = epoch
            best_ref_emb = ref_emb.numpy().copy()
        elif patience > 0 and (epoch - best_epoch) >= patience:
            break

    final_ref_emb = (best_ref_emb if best_ref_emb is not None else ref_emb.numpy()).reshape(1, -1).astype(np.float32)
    ref_batch = np.repeat(final_ref_emb, N, axis=0).astype(np.float32)
    outputs = head.predict([ref_batch, np.asarray(query_embeddings, dtype=np.float32)], batch_size=batch_size, verbose=0)
    if not isinstance(outputs, (list, tuple)):
        outputs = [outputs]

    onoff_prob = _to_probability(np.asarray(outputs[onoff_idx], dtype=np.float32).reshape(-1))
    onoff_threshold, onoff_f1 = _best_prob_threshold(np.asarray(targets_on, dtype=np.int32), onoff_prob)

    appliance_params: Dict[str, float] = {
        "onoff_threshold": float(onoff_threshold),
    }

    if y_power is not None and reg_idx is not None:
        pred_power_norm = np.asarray(outputs[reg_idx], dtype=np.float32).reshape(-1)
        pred_power_w = _denorm_power(pred_power_norm, settings)
        power_threshold, power_f1 = _best_power_threshold(np.asarray(targets_power, dtype=np.float32), pred_power_w)
        appliance_params["power_threshold"] = float(power_threshold)
    else:
        power_f1 = None

    stats = {
        "epochs_requested": int(epochs),
        "epochs_ran": int(len(total_losses)),
        "final_loss": float(total_losses[-1]),
        "min_loss": float(min(total_losses)),
        "final_cls_loss": float(cls_losses[-1]),
        "min_cls_loss": float(min(cls_losses)),
        "final_reg_loss": float(reg_losses[-1]) if y_power is not None else None,
        "min_reg_loss": float(min(reg_losses)) if y_power is not None else None,
        "n_samples": int(N),
        "embedding_dim": int(D),
        "batch_size": int(batch_size),
        "lr": float(lr),
        "early_stopped": bool(len(total_losses) < epochs),
        "steps_per_epoch": int(steps_per_epoch),
        "fine_tune_target": fine_tune_target,
        "onoff_threshold": float(onoff_threshold),
        "onoff_f1": float(onoff_f1),
        "power_threshold": float(appliance_params.get("power_threshold", 0.0)),
        "power_f1": None if power_f1 is None else float(power_f1),
    }

    return final_ref_emb.reshape(-1).tolist(), stats, appliance_params
