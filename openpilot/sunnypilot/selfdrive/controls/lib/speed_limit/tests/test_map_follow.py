"""
HW1 fork, map follow (2026-11-22): the map limit is the cruise ceiling instead of the stalk,
a lower limit ahead is reached before the sign's line, and a speed-limit braking floor.
"""
import time
from types import SimpleNamespace

import pytest

from openpilot.cereal import custom
from openpilot.common.constants import CV
from openpilot.common.params import Params
from openpilot.common.realtime import DT_MDL
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit import LIMIT_ADAPT_ACC, LIMIT_MIN_ACC, \
  LIMIT_AHEAD_MARGIN_TIME, LIMIT_AHEAD_MARGIN_MIN, MAP_FOLLOW_HOLD_TIME
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.common import Mode, Policy
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.map_follow import MapFollow, ENGAGE_GUARD_TIME
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.speed_limit_resolver import SpeedLimitResolver

SpeedLimitSource = custom.LongitudinalPlanSP.SpeedLimit.Source
LongitudinalPlanSource = custom.LongitudinalPlanSP.LongitudinalPlanSource

KPH = CV.KPH_TO_MS


def kph(v):
  return v * KPH


def make_map_follow(enabled=True, mode=Mode.assist, max_kph=None):
  params = Params()
  params.put_bool("MapFollowEnabled", enabled)
  params.put("SpeedLimitMode", int(mode))
  if max_kph is not None:
    params.put("MapFollowMaxKph", max_kph)
  return MapFollow(params)


def run(mf, frames, long_enabled=True, cluster=50, limit=90, valid=True, force_decel=False):
  for _ in range(frames):
    mf.update(long_enabled, force_decel, kph(cluster), kph(limit), valid)


def engage(mf, cluster=50, limit=90):
  run(mf, int(ENGAGE_GUARD_TIME / DT_MDL) + 2, cluster=cluster, limit=limit)


class TestMapFollow:
  def test_map_limit_is_the_ceiling_above_the_stalk(self):
    mf = make_map_follow()
    engage(mf, cluster=50, limit=90)
    assert mf.active
    assert mf.ceiling == pytest.approx(kph(90))

  def test_map_limit_is_the_ceiling_below_the_stalk(self):
    mf = make_map_follow()
    engage(mf, cluster=120, limit=50)
    assert mf.active
    assert mf.ceiling == pytest.approx(kph(50))

  def test_cap_defaults_to_130(self):
    mf = make_map_follow()
    engage(mf, cluster=50, limit=150)
    assert mf.ceiling == pytest.approx(kph(130))

  def test_owner_cap(self):
    mf = make_map_follow(max_kph=110)
    engage(mf, cluster=50, limit=130)
    assert mf.ceiling == pytest.approx(kph(110))

  def test_off_when_disabled_or_not_assist(self):
    for mf in (make_map_follow(enabled=False), make_map_follow(mode=Mode.information)):
      engage(mf)
      assert not mf.active

  def test_off_when_not_engaged_or_force_decel(self):
    mf = make_map_follow()
    run(mf, 30, long_enabled=False)
    assert not mf.active
    engage(mf)
    run(mf, 1, force_decel=True)
    assert not mf.active

  def test_no_map_falls_back_to_the_stalk(self):
    mf = make_map_follow()
    run(mf, 30, valid=False, limit=0)
    assert not mf.active

  def test_short_map_gap_is_held_long_gap_is_not(self):
    mf = make_map_follow()
    engage(mf, limit=90)
    hold = int(MAP_FOLLOW_HOLD_TIME / DT_MDL)
    run(mf, hold - 2, valid=False, limit=0)
    assert mf.active and mf.ceiling == pytest.approx(kph(90))
    run(mf, 4, valid=False, limit=0)
    assert not mf.active

  def test_stalk_change_overrides_until_next_limit(self):
    mf = make_map_follow()
    engage(mf, cluster=50, limit=90)
    assert mf.active
    run(mf, 1, cluster=60, limit=90)  # driver moves the stalk
    assert mf.override and not mf.active
    run(mf, 50, cluster=60, limit=90)  # same limit: the stalk still rules
    assert not mf.active
    run(mf, 1, cluster=60, limit=70)  # next sign
    assert mf.active and mf.ceiling == pytest.approx(kph(70))

  def test_engagement_itself_is_not_an_override(self):
    mf = make_map_follow()
    run(mf, 1, cluster=40, limit=90)
    run(mf, 2, cluster=55, limit=90)  # stalk value settles inside the guard window
    run(mf, 10, cluster=55, limit=90)
    assert mf.active and not mf.override

  def test_reengagement_clears_override(self):
    mf = make_map_follow()
    engage(mf)
    run(mf, 1, cluster=60)
    assert mf.override
    run(mf, 1, long_enabled=False)
    engage(mf, cluster=60)
    assert mf.active and not mf.override


def resolver_sm(mocker, v_limit, ahead, ahead_dist, gps_age=0.):
  live_map = SimpleNamespace(speedLimit=v_limit, speedLimitValid=v_limit > 0, speedLimitAhead=ahead,
                             speedLimitAheadValid=ahead > 0, speedLimitAheadDistance=ahead_dist)
  car_sp = SimpleNamespace(speedLimit=0.)
  gps = SimpleNamespace(hasFix=True)
  sm = mocker.MagicMock()
  sm.__getitem__.side_effect = lambda key: {'liveMapDataSP': live_map, 'carStateSP': car_sp, 'gpsLocation': gps,
                                            'gpsLocationExternal': gps}[key]
  sm.alive = {'gpsLocation': True, 'gpsLocationExternal': True}
  now = time.monotonic() - gps_age
  sm.recv_time = {'gpsLocation': now, 'gpsLocationExternal': now}
  return sm


def braking_point(v, v_next):
  return (v ** 2 - v_next ** 2) / (2 * -LIMIT_ADAPT_ACC) + max(LIMIT_AHEAD_MARGIN_TIME * v, LIMIT_AHEAD_MARGIN_MIN)


class TestResolverAhead:
  def make(self):
    r = SpeedLimitResolver()
    r.policy = Policy.combined
    return r

  def test_switches_early_enough_to_reach_the_limit_before_the_line(self, mocker):
    r = self.make()
    v, v_next = kph(90), kph(50)
    start = braking_point(v, v_next)
    r.update(v, resolver_sm(mocker, kph(90), v_next, start + 30))
    assert r.speed_limit == pytest.approx(kph(90))
    r.update(v, resolver_sm(mocker, kph(90), v_next, start - 1))
    assert r.speed_limit == pytest.approx(v_next)
    assert r.source == SpeedLimitSource.map
    margin = max(LIMIT_AHEAD_MARGIN_TIME * v, LIMIT_AHEAD_MARGIN_MIN)
    assert r.distance == pytest.approx(start - 1 - margin, abs=1.)
    assert r.distance_to_line == pytest.approx(start - 1, abs=1.)

  def test_stays_on_the_new_limit_once_slowed_down(self, mocker):
    # the old FIXME-SP block switched back to the higher limit as soon as v_ego < next limit
    r = self.make()
    v_next = kph(50)
    r.update(kph(90), resolver_sm(mocker, kph(90), v_next, 200))
    assert r.speed_limit == pytest.approx(v_next)
    r.update(kph(49), resolver_sm(mocker, kph(90), v_next, 40))
    assert r.speed_limit == pytest.approx(v_next)

  def test_latch_ends_at_the_sign_and_on_a_new_announcement(self, mocker):
    r = self.make()
    r.update(kph(90), resolver_sm(mocker, kph(90), kph(50), 200))
    r.update(kph(50), resolver_sm(mocker, kph(50), 0., 0.))  # passed the sign
    assert r.speed_limit == pytest.approx(kph(50)) and r.distance_to_line == 0.
    r = self.make()
    r.update(kph(90), resolver_sm(mocker, kph(90), kph(50), 200))
    r.update(kph(80), resolver_sm(mocker, kph(90), kph(70), 900))  # a different limit announced, far away
    assert r.speed_limit == pytest.approx(kph(90))

  def test_higher_limit_ahead_waits_for_the_line(self, mocker):
    r = self.make()
    r.update(kph(50), resolver_sm(mocker, kph(50), kph(90), 5))
    assert r.speed_limit == pytest.approx(kph(50))


class TestBrakingFloor:
  """LongitudinalPlannerSP._cruise_accel_min, called on a minimal stand-in for the planner."""

  @staticmethod
  def floor(source, v_target, v_ego, map_follow_active=False, distance=0., distance_to_line=0., resolver_source=None):
    from openpilot.sunnypilot.selfdrive.controls.lib.longitudinal_planner import LongitudinalPlannerSP, CRUISE_ACCEL_MIN_MANUAL
    me = SimpleNamespace(source=source, output_v_target=v_target, map_follow=SimpleNamespace(active=map_follow_active),
                         resolver=SimpleNamespace(distance=distance, distance_to_line=distance_to_line,
                                                  source=resolver_source if resolver_source is not None else SpeedLimitSource.map))
    return LongitudinalPlannerSP._cruise_accel_min(me, v_ego), CRUISE_ACCEL_MIN_MANUAL

  def test_manual_reduction_keeps_the_gentle_floor(self):
    got, manual = self.floor(LongitudinalPlanSource.cruise, kph(50), kph(90))
    assert got == manual == -0.5

  def test_speed_limit_target_brakes_at_minus_one(self):
    got, _ = self.floor(LongitudinalPlanSource.cruise, kph(50), kph(90), map_follow_active=True, distance=400.)
    assert got == pytest.approx(LIMIT_ADAPT_ACC)
    got, _ = self.floor(LongitudinalPlanSource.speedLimitAssist, kph(50), kph(90), distance=0.)
    assert got == pytest.approx(LIMIT_ADAPT_ACC)

  def test_late_announcement_brakes_harder_but_not_past_minus_one_and_a_half(self):
    v, vt = kph(90), kph(50)
    got, _ = self.floor(LongitudinalPlanSource.cruise, vt, v, map_follow_active=True, distance=150.)
    assert got == pytest.approx((vt ** 2 - v ** 2) / (2 * 150.))
    assert LIMIT_MIN_ACC < got < LIMIT_ADAPT_ACC
    got, _ = self.floor(LongitudinalPlanSource.cruise, vt, v, map_follow_active=True, distance=30.)
    assert got == pytest.approx(LIMIT_MIN_ACC)

  def test_inside_the_margin_aims_at_the_line(self):
    v, vt = kph(60), kph(50)
    got, _ = self.floor(LongitudinalPlanSource.cruise, vt, v, map_follow_active=True, distance=0., distance_to_line=40.)
    assert got == pytest.approx(max((vt ** 2 - v ** 2) / (2 * 40.), LIMIT_MIN_ACC))

  def test_no_floor_change_when_not_braking(self):
    got, manual = self.floor(LongitudinalPlanSource.cruise, kph(90), kph(50), map_follow_active=True)
    assert got == manual
