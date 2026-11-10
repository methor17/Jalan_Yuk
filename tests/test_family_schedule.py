"""Regression tests for mixed ages, real outbound/return dates and timetable caps."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import clean_config, fixed_costs, item_cost, clean_place, transport_ledger, generate_plan, recalculate
from test_planner import CONFIG, PLACES

BASE={**CONFIG, 'days':3, 'children':0, 'adults':2, 'seniors':0,
      'start_date':'2027-01-01','depart_date':'2026-12-31','depart_time':'21:00',
      'destination_arrival_date':'2027-01-01','destination_arrival_time':'07:30',
      'arrival_time':'10:00','return_date':'2027-01-03','return_time':'18:00',
      'home_arrival_date':'2027-01-04','home_arrival_time':'00:30',
      'outbound_mode':'kereta','return_mode':'kereta','outbound_fare':175000,'return_fare':225000}

class FamilyScheduleTests(unittest.TestCase):
    def test_overnight_cross_year_start(self):
        c=clean_config(BASE)
        self.assertEqual(c['days'],3)
        self.assertEqual(c['depart_date'],'2026-12-31')
        self.assertEqual(c['start_date'],'2027-01-01')
        self.assertEqual(c['home_arrival_date'],'2027-01-04')
        plan=generate_plan(BASE,PLACES)
        self.assertEqual(plan['itinerary'][0]['date'],'2027-01-01')
        self.assertEqual(plan['itinerary'][0]['slots'][0]['start'],'10:00')
        self.assertEqual(plan['summary']['travel_timeline']['berangkat'],'2026-12-31 21:00')
        self.assertEqual(plan['summary']['travel_timeline']['tiba_rumah'],'2027-01-04 00:30')
    def test_infant_under2_not_counted_train_when_one_per_adult(self):
        c=clean_config({**BASE,'infants_under_2':2,'adults':2})
        t=transport_ledger(c,'pergi')
        self.assertEqual(t['gratis_bayi'],2)
        self.assertEqual(t['total'],175000*2)
    def test_age2_can_be_free_train_under3(self):
        c=clean_config({**BASE,'adults':1,'children_2_plus':1,'children_age_2':1})
        t=transport_ledger(c,'pergi')
        self.assertEqual(t['gratis_anak_usia_2'],1)
        self.assertEqual(t['total'],175000)
    def test_children_over_age2_pay_train_fare(self):
        c=clean_config({**BASE,'adults':1,'children_2_plus':2,'children_age_2':1})
        self.assertEqual(transport_ledger(c,'pergi')['total'],350000)
    def test_free_quota_one_per_adult_combines_baby_and_2yo(self):
        c=clean_config({**BASE,'adults':1,'infants_under_2':1,'children_2_plus':1,'children_age_2':1})
        t=transport_ledger(c,'pergi')
        self.assertEqual(t['gratis_bayi'],1)
        self.assertEqual(t['gratis_anak_usia_2'],0)
        self.assertEqual(t['total'],350000)
    def test_train_with_seat_all_pay(self):
        c=clean_config({**BASE,'adults':1,'infants_under_2':1,'children_2_plus':1,'children_age_2':1,'train_infant_without_seat':False,'train_age2_without_seat':False})
        t=transport_ledger(c,'pergi')
        self.assertEqual(t['total'],3*175000)
    def test_train_age2_can_be_lap_without_baby_lap(self):
        c=clean_config({**BASE,'adults':1,'infants_under_2':1,'children_2_plus':1,'children_age_2':1,'train_infant_without_seat':False,'train_age2_without_seat':True})
        self.assertEqual(transport_ledger(c,'pergi')['total'],2*175000)
    def test_train_age2_selected_seat_pays(self):
        c=clean_config({**BASE,'adults':1,'children_2_plus':1,'children_age_2':1,'train_age2_without_seat':False})
        self.assertEqual(transport_ledger(c,'pergi')['total'],2*175000)
    def test_plane_infant_lap_has_nonzero_configurable_fare(self):
        c=clean_config({**BASE,'adults':1,'children_2_plus':1,'infants_under_2':1,'outbound_mode':'pesawat','outbound_fare':1000000,'flight_infant_percent':12})
        self.assertEqual(transport_ledger(c,'pergi')['total'],2_120_000)
    def test_extra_plane_infant_seat_full(self):
        c=clean_config({**BASE,'adults':1,'infants_under_2':2,'outbound_mode':'pesawat','outbound_fare':1000000})
        self.assertEqual(transport_ledger(c,'pergi')['total'],2_100_000)
    def test_mixed_transport_outbound_and_return(self):
        c=clean_config({**BASE,'adults':1,'infants_under_2':1,'outbound_mode':'kereta','return_mode':'pesawat','outbound_fare':200000,'return_fare':1000000,'flight_infant_percent':10})
        self.assertEqual(fixed_costs(c)['transport_antar_kota'],1_300_000)
    def test_car_cost_per_vehicle_counts_infants_for_seating(self):
        c=clean_config({**BASE,'adults':2,'children_2_plus':2,'infants_under_2':1,'outbound_mode':'mobil','car_capacity':4,'outbound_fare':600000})
        t=transport_ledger(c,'pergi')
        self.assertEqual(t['jumlah_kendaraan'],2)
        self.assertEqual(t['total'],1_200_000)
    def test_hotel_nights_begin_with_destination_arrival(self):
        c=clean_config({**BASE,'destination_arrival_date':'2026-12-31','destination_arrival_time':'23:00'})
        self.assertEqual(fixed_costs(c)['hotel'],3*300000)
    def test_hotel_infants_share_bed_by_default(self):
        c=clean_config({**BASE,'adults':2,'infants_under_2':1,'room_capacity':2})
        self.assertEqual(fixed_costs(c)['hotel'],2*300000)
        c2=clean_config({**BASE,'adults':2,'infants_under_2':1,'room_capacity':2,'infant_uses_bed':True})
        self.assertEqual(fixed_costs(c2)['hotel'],2*2*300000)
    def test_age2_ticket_percent_can_be_separate(self):
        c=clean_config({**BASE,'adults':1,'children_2_plus':2,'children_age_2':1,'infants_under_2':1,'child_activity_percent':80,'age2_activity_percent':0,'infant_activity_percent':0})
        p=clean_place({**PLACES[0],'price':100000})
        self.assertEqual(item_cost(p,c),180000)
    def test_age2_food_and_infant_food_can_be_separate(self):
        c=clean_config({**BASE,'adults':1,'children_2_plus':2,'children_age_2':1,'infants_under_2':1,'child_food_percent':75,'age2_food_percent':50,'infant_food_percent':20})
        p=clean_place({**PLACES[-1],'price':100000})
        self.assertEqual(item_cost(p,c),245000)
    def test_age2_local_cost_can_be_separate(self):
        c=clean_config({**BASE,'adults':1,'children_2_plus':2,'children_age_2':1,'infants_under_2':1,'local_per_person_day':100000,'local_child_percent':100,'local_age2_percent':50,'local_infant_percent':0})
        self.assertEqual(fixed_costs(c)['transport_lokal'],250000*3)
    def test_not_scheduled_after_return_limit_not_charged(self):
        c={**BASE,'return_date':'2027-01-01','return_time':'12:00','home_arrival_date':'2027-01-01','home_arrival_time':'16:00', 'return_buffer_minutes':90}
        plan=generate_plan(c,PLACES)
        day=plan['itinerary'][0]
        self.assertEqual(day['window_end'],'10:30')
        self.assertEqual(len(plan['itinerary']),1)
        self.assertTrue(any(s['status']=='tidak_terjadwal' for s in day['slots']))
        self.assertTrue(all(s['end']<='10:30' for s in day['slots'] if s['status']=='scheduled'))
        self.assertEqual(day['cost'],sum(s['cost'] for s in day['slots']))
        self.assertTrue(all(s['cost']==0 for s in day['slots'] if s['status']=='tidak_terjadwal'))
    def test_early_return_no_visits_on_return_day(self):
        c={**BASE,'return_time':'08:00','home_arrival_date':'2027-01-03','home_arrival_time':'10:00'}
        plan=generate_plan(c,PLACES)
        last=plan['itinerary'][-1]
        self.assertEqual(last['cost'],0)
        self.assertFalse(any(s['status']=='scheduled' for s in last['slots']))
    def test_reschedule_return_earlier_recalculates_cost(self):
        plan=generate_plan(BASE,PLACES)
        earlier={**BASE,'return_time':'11:00','home_arrival_date':'2027-01-03','home_arrival_time':'17:00'}
        updated=recalculate(earlier,plan['itinerary'])
        self.assertLess(updated['summary']['breakdown']['wisata']+updated['summary']['breakdown']['kuliner'],plan['summary']['breakdown']['wisata']+plan['summary']['breakdown']['kuliner'])
        self.assertEqual(updated['itinerary'][-1]['cost'],0)
    def test_return_duration_derived_from_date(self):
        c=clean_config({**BASE,'days':9,'return_date':'2027-01-02','home_arrival_date':'2027-01-02','home_arrival_time':'23:00'})
        self.assertEqual(c['days'],2)
    def test_reject_wrong_time_order(self):
        cases=[
            {'depart_date':'2027-01-02'},
            {'destination_arrival_time':'23:00'},
            {'arrival_time':'06:00'},
            {'return_date':'2026-12-31'},
            {'home_arrival_date':'2027-01-02'},
        ]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(ValueError):clean_config({**BASE,**change})
    def test_reject_over_14_days(self):
        with self.assertRaises(ValueError):clean_config({**BASE,'return_date':'2027-01-20','home_arrival_date':'2027-01-21'})
    def test_reject_age2_outside_child_count(self):
        with self.assertRaises(ValueError):clean_config({**BASE,'children_2_plus':1,'children_age_2':2})
    def test_reject_infant_without_adult(self):
        with self.assertRaises(ValueError):clean_config({**BASE,'adults':0,'seniors':0,'children_2_plus':1,'infants_under_2':1})
    def test_legacy_v2_data_still_works(self):
        c=clean_config(CONFIG)
        self.assertEqual(c['return_date'],( __import__('datetime').date.fromisoformat(CONFIG['start_date'])+ __import__('datetime').timedelta(days=CONFIG['days']-1)).isoformat())
        self.assertEqual(fixed_costs(c)['transport_antar_kota'],300000)

if __name__=='__main__':unittest.main()
