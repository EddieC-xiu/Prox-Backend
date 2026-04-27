import sys
sys.path.insert(0, ".")
from config.supabase import get_supabase_client

sb = get_supabase_client()

rows = [
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91801",
    "latitude": 34.0995066,
    "longitude": -118.1196743,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92801",
    "latitude": 33.8402595,
    "longitude": -117.9400825,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94509",
    "latitude": 38.0006131,
    "longitude": -121.8431842,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93420",
    "latitude": 35.1221104,
    "longitude": -120.606099,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93422",
    "latitude": 35.4754391,
    "longitude": -120.6568387,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95603",
    "latitude": 38.9400355,
    "longitude": -121.0977277,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91702",
    "latitude": 34.1344391,
    "longitude": -117.9045823,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93301",
    "latitude": 35.3898685,
    "longitude": -119.0252247,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93309",
    "latitude": 35.318155,
    "longitude": -119.0410028,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93309",
    "latitude": 35.3555144,
    "longitude": -119.0573232,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93312",
    "latitude": 35.3858878,
    "longitude": -119.1121252,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93306",
    "latitude": 35.3928626,
    "longitude": -118.9691478,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91706",
    "latitude": 34.0706626,
    "longitude": -117.979722,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92220",
    "latitude": 33.9261969,
    "longitude": -116.9092942,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90201",
    "latitude": 33.9705605,
    "longitude": -118.1768816,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90706",
    "latitude": 33.8884412,
    "longitude": -118.1239078,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93514",
    "latitude": 37.3734604,
    "longitude": -118.3946669,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92225",
    "latitude": 33.6113895,
    "longitude": -114.589003,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90620",
    "latitude": 33.8471346,
    "longitude": -118.0268232,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "86442",
    "latitude": 35.1068968,
    "longitude": -114.5975507,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91505",
    "latitude": 34.1741868,
    "longitude": -118.3508717,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91505",
    "latitude": 34.1597869,
    "longitude": -118.3450077,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93010",
    "latitude": 34.2206772,
    "longitude": -119.0394198,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92624",
    "latitude": 33.4678175,
    "longitude": -117.6780431,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92008",
    "latitude": 33.1618981,
    "longitude": -117.3435929,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95608",
    "latitude": 38.6325881,
    "longitude": -121.3296891,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93013",
    "latitude": 34.3972669,
    "longitude": -119.5188584,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90810",
    "latitude": 33.8460908,
    "longitude": -118.2061599,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91311",
    "latitude": 34.2584893,
    "longitude": -118.5786583,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91710",
    "latitude": 34.0327991,
    "longitude": -117.6909857,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91709",
    "latitude": 33.9843087,
    "longitude": -117.7146733,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91911",
    "latitude": 32.5938966,
    "longitude": -117.0658504,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91910",
    "latitude": 32.651978,
    "longitude": -117.0898987,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91910",
    "latitude": 32.6391539,
    "longitude": -117.0510149,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95610",
    "latitude": 38.6653851,
    "longitude": -121.2708122,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93612",
    "latitude": 36.8072074,
    "longitude": -119.7266555,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92236",
    "latitude": 33.6863383,
    "longitude": -116.1803998,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92324",
    "latitude": 34.0745525,
    "longitude": -117.3146173,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90220",
    "latitude": 33.8945392,
    "longitude": -118.2209556,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92880",
    "latitude": 33.8933904,
    "longitude": -117.5658187,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92118",
    "latitude": 32.6972763,
    "longitude": -117.1712342,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92627",
    "latitude": 33.6427387,
    "longitude": -117.9282514,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91722",
    "latitude": 34.0868539,
    "longitude": -117.9061343,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94014",
    "latitude": 37.6965018,
    "longitude": -122.4639733,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94526",
    "latitude": 37.8241827,
    "longitude": -121.9923636,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93215",
    "latitude": 35.7778394,
    "longitude": -119.249149,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91765",
    "latitude": 34.0218656,
    "longitude": -117.809253,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91010",
    "latitude": 34.1406323,
    "longitude": -117.979356,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92880",
    "latitude": 33.9766602,
    "longitude": -117.5742423,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92020",
    "latitude": 32.8082348,
    "longitude": -116.9750322,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92021",
    "latitude": 32.8239354,
    "longitude": -116.9037052,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92020",
    "latitude": 32.8009294,
    "longitude": -117.003725,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92243",
    "latitude": 32.7978549,
    "longitude": -115.5717022,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91731",
    "latitude": 34.0723483,
    "longitude": -118.0311879,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95624",
    "latitude": 38.4101364,
    "longitude": -121.3771229,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92024",
    "latitude": 33.0463621,
    "longitude": -117.2821186,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91436",
    "latitude": 34.1599361,
    "longitude": -118.5000532,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92025",
    "latitude": 33.1223882,
    "longitude": -117.0877744,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94533",
    "latitude": 38.2752533,
    "longitude": -122.0359767,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92335",
    "latitude": 34.1074418,
    "longitude": -117.4329672,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92708",
    "latitude": 33.7146428,
    "longitude": -117.9727672,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94538",
    "latitude": 37.5514026,
    "longitude": -121.9806357,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93721",
    "latitude": 36.7285969,
    "longitude": -119.7889974,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93710",
    "latitude": 36.8210105,
    "longitude": -119.7882884,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93711",
    "latitude": 36.8099941,
    "longitude": -119.8518509,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93703",
    "latitude": 36.77276,
    "longitude": -119.7923025,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93720",
    "latitude": 36.850557,
    "longitude": -119.77617,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92831",
    "latitude": 33.8746711,
    "longitude": -117.8877843,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "85234",
    "latitude": 33.3637009,
    "longitude": -111.7924819,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95020",
    "latitude": 36.999856,
    "longitude": -121.5623764,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91206",
    "latitude": 34.1486367,
    "longitude": -118.234705,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93117",
    "latitude": 34.4307886,
    "longitude": -119.8749323,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91344",
    "latitude": 34.2567553,
    "longitude": -118.4857483,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93230",
    "latitude": 36.3312746,
    "longitude": -119.655304,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94541",
    "latitude": 37.661459,
    "longitude": -122.1163201,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92545",
    "latitude": 33.7459039,
    "longitude": -116.9983949,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89052",
    "latitude": 36.0070342,
    "longitude": -115.1122355,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92345",
    "latitude": 34.4697988,
    "longitude": -117.3335632,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92346",
    "latitude": 34.1221978,
    "longitude": -117.2038952,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90042",
    "latitude": 34.1111518,
    "longitude": -118.1875064,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92647",
    "latitude": 33.7287078,
    "longitude": -118.0086554,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92646",
    "latitude": 33.6716355,
    "longitude": -117.9699303,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90255",
    "latitude": 33.9733268,
    "longitude": -118.2115433,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90303",
    "latitude": 33.9447344,
    "longitude": -118.3264275,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90302",
    "latitude": 33.9766435,
    "longitude": -118.3663255,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92604",
    "latitude": 33.7064765,
    "longitude": -117.7872555,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90631",
    "latitude": 33.9186412,
    "longitude": -117.966586,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91941",
    "latitude": 32.7461632,
    "longitude": -116.9596243,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91744",
    "latitude": 34.037697,
    "longitude": -117.948853,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92253",
    "latitude": 33.7086389,
    "longitude": -116.272936,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92653",
    "latitude": 33.576969,
    "longitude": -117.7013246,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92677",
    "latitude": 33.5227028,
    "longitude": -117.7143367,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92630",
    "latitude": 33.6211241,
    "longitude": -117.7040397,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90713",
    "latitude": 33.834735,
    "longitude": -118.1178913,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93536",
    "latitude": 34.6887489,
    "longitude": -118.1676714,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89102",
    "latitude": 36.1585639,
    "longitude": -115.2001847,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89101",
    "latitude": 36.1743275,
    "longitude": -115.1181928,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89117",
    "latitude": 36.1425556,
    "longitude": -115.2762066,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89108",
    "latitude": 36.1943236,
    "longitude": -115.2076274,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89121",
    "latitude": 36.1162545,
    "longitude": -115.0931201,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90260",
    "latitude": 33.8936075,
    "longitude": -118.3534943,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95240",
    "latitude": 38.1310846,
    "longitude": -121.2689077,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90814",
    "latitude": 33.7631723,
    "longitude": -118.1518674,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90813",
    "latitude": 33.7831148,
    "longitude": -118.184216,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90807",
    "latitude": 33.8392675,
    "longitude": -118.1843988,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90021",
    "latitude": 34.0273617,
    "longitude": -118.2418386,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90044",
    "latitude": 33.9648022,
    "longitude": -118.2922332,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90059",
    "latitude": 33.9170056,
    "longitude": -118.2548975,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90033",
    "latitude": 34.0406314,
    "longitude": -118.2130508,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90029",
    "latitude": 34.0879412,
    "longitude": -118.3096439,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90006",
    "latitude": 34.0475457,
    "longitude": -118.3047793,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90036",
    "latitude": 34.0627019,
    "longitude": -118.349581,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90064",
    "latitude": 34.0366392,
    "longitude": -118.4375995,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90019",
    "latitude": 34.047905,
    "longitude": -118.3353874,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90007",
    "latitude": 34.0225998,
    "longitude": -118.2921847,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90057",
    "latitude": 34.0698396,
    "longitude": -118.2782884,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90016",
    "latitude": 34.0282091,
    "longitude": -118.3354677,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90017",
    "latitude": 34.0475719,
    "longitude": -118.2628036,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90031",
    "latitude": 34.0754187,
    "longitude": -118.2165712,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90035",
    "latitude": 34.0438277,
    "longitude": -118.3792477,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90002",
    "latitude": 33.9478099,
    "longitude": -118.2306821,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90262",
    "latitude": 33.9343161,
    "longitude": -118.2138276,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93637",
    "latitude": 36.9768437,
    "longitude": -120.0836742,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95340",
    "latitude": 37.2981784,
    "longitude": -120.4842616,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95035",
    "latitude": 37.4477897,
    "longitude": -121.9024178,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92691",
    "latitude": 33.6208716,
    "longitude": -117.659527,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95350",
    "latitude": 37.6845509,
    "longitude": -121.0497834,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95354",
    "latitude": 37.6443344,
    "longitude": -120.9914149,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90640",
    "latitude": 34.0314043,
    "longitude": -118.1261766,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93020",
    "latitude": 34.2811577,
    "longitude": -118.8646882,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92553",
    "latitude": 33.9185366,
    "longitude": -117.2253006,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94040",
    "latitude": 37.3787523,
    "longitude": -122.0716707,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92562",
    "latitude": 33.5586441,
    "longitude": -117.1999041,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91606",
    "latitude": 34.2259806,
    "longitude": -118.397842,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89032",
    "latitude": 36.2389598,
    "longitude": -115.1456531,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91950",
    "latitude": 32.6760357,
    "longitude": -117.0936142,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91320",
    "latitude": 34.1827198,
    "longitude": -118.9238043,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91324",
    "latitude": 34.2585458,
    "longitude": -118.5376644,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90650",
    "latitude": 33.9238106,
    "longitude": -118.100426,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94601",
    "latitude": 37.7726579,
    "longitude": -122.2174877,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92054",
    "latitude": 33.1895723,
    "longitude": -117.3600789,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91764",
    "latitude": 34.0790326,
    "longitude": -117.6274403,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92867",
    "latitude": 33.8100469,
    "longitude": -117.8390188,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95965",
    "latitude": 39.4966353,
    "longitude": -121.5736115,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93036",
    "latitude": 34.2218488,
    "longitude": -119.1788566,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93033",
    "latitude": 34.176725,
    "longitude": -119.193268,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91331",
    "latitude": 34.2678667,
    "longitude": -118.4247532,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92264",
    "latitude": 33.8154807,
    "longitude": -116.4922236,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93551",
    "latitude": 34.5959946,
    "longitude": -118.1449087,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93551",
    "latitude": 34.6295639,
    "longitude": -118.2204545,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91103",
    "latitude": 34.1527124,
    "longitude": -118.1508142,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91107",
    "latitude": 34.1466842,
    "longitude": -118.0831655,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93446",
    "latitude": 35.6364084,
    "longitude": -120.6931673,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93446",
    "latitude": 35.6239553,
    "longitude": -120.660523,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94954",
    "latitude": 38.2534989,
    "longitude": -122.6380405,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "85016",
    "latitude": 33.4956693,
    "longitude": -112.0223196,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "85009",
    "latitude": 33.4641405,
    "longitude": -112.1527252,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "85053",
    "latitude": 33.6266412,
    "longitude": -112.1327753,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "85032",
    "latitude": 33.6124116,
    "longitude": -111.9761895,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94523",
    "latitude": 37.9476312,
    "longitude": -122.0585965,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94588",
    "latitude": 37.6994974,
    "longitude": -121.9065079,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91768",
    "latitude": 34.0784634,
    "longitude": -117.7537384,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93257",
    "latitude": 36.0648336,
    "longitude": -119.0492587,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92064",
    "latitude": 32.9508017,
    "longitude": -117.0636862,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95670",
    "latitude": 38.616848,
    "longitude": -121.2707732,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91730",
    "latitude": 34.1202082,
    "longitude": -117.6169748,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90275",
    "latitude": 33.7611508,
    "longitude": -118.3117785,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92373",
    "latitude": 34.0635542,
    "longitude": -117.2133726,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90277",
    "latitude": 33.8518971,
    "longitude": -118.3903627,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90277",
    "latitude": 33.8208485,
    "longitude": -118.3843689,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94063",
    "latitude": 37.4864379,
    "longitude": -122.213877,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "89502",
    "latitude": 39.5068272,
    "longitude": -119.798965,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92507",
    "latitude": 33.9834495,
    "longitude": -117.3650504,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92503",
    "latitude": 33.9169028,
    "longitude": -117.4649941,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92504",
    "latitude": 33.9444932,
    "longitude": -117.4159,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92507",
    "latitude": 33.9414981,
    "longitude": -117.2803836,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95678",
    "latitude": 38.7470997,
    "longitude": -121.2739372,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95841",
    "latitude": 38.6604609,
    "longitude": -121.3515943,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95818",
    "latitude": 38.5577987,
    "longitude": -121.4753526,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95831",
    "latitude": 38.4943852,
    "longitude": -121.504777,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95825",
    "latitude": 38.59706,
    "longitude": -121.3814106,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95834",
    "latitude": 38.629135,
    "longitude": -121.4769392,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95820",
    "latitude": 38.5285468,
    "longitude": -121.4458411,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93901",
    "latitude": 36.6795373,
    "longitude": -121.6455342,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92115",
    "latitude": 32.7625364,
    "longitude": -117.0635231,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92117",
    "latitude": 32.8333901,
    "longitude": -117.1795324,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92101",
    "latitude": 32.7129344,
    "longitude": -117.1510158,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92110",
    "latitude": 32.7491458,
    "longitude": -117.2035795,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92126",
    "latitude": 32.9155463,
    "longitude": -117.1221405,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92124",
    "latitude": 32.82114,
    "longitude": -117.1011355,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92104",
    "latitude": 32.7480847,
    "longitude": -117.1403744,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91773",
    "latitude": 34.108107,
    "longitude": -117.8273878,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91340",
    "latitude": 34.2985031,
    "longitude": -118.4387891,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94118",
    "latitude": 37.7823468,
    "longitude": -122.4652117,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95122",
    "latitude": 37.3387159,
    "longitude": -121.8414796,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95124",
    "latitude": 37.2648461,
    "longitude": -121.9164096,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95126",
    "latitude": 37.3232548,
    "longitude": -121.9102866,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95123",
    "latitude": 37.2506763,
    "longitude": -121.8304217,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93401",
    "latitude": 35.2817755,
    "longitude": -120.6556525,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92078",
    "latitude": 33.1371198,
    "longitude": -117.1809074,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94403",
    "latitude": 37.554948,
    "longitude": -122.2938314,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94805",
    "latitude": 37.9506363,
    "longitude": -122.3305033,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90732",
    "latitude": 33.7240262,
    "longitude": -118.3135075,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94901",
    "latitude": 37.9573154,
    "longitude": -122.5067691,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92706",
    "latitude": 33.7613163,
    "longitude": -117.8892697,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92704",
    "latitude": 33.7258418,
    "longitude": -117.8857939,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93101",
    "latitude": 34.4189049,
    "longitude": -119.6921436,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93105",
    "latitude": 34.439064,
    "longitude": -119.7528284,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95050",
    "latitude": 37.3531106,
    "longitude": -121.9610865,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91321",
    "latitude": 34.3783739,
    "longitude": -118.5480908,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93454",
    "latitude": 34.9291555,
    "longitude": -120.4371134,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95407",
    "latitude": 38.4085623,
    "longitude": -122.7138191,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92071",
    "latitude": 32.8564095,
    "longitude": -116.9721521,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93955",
    "latitude": 36.6089287,
    "longitude": -121.8553043,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93065",
    "latitude": 34.2705912,
    "longitude": -118.7603115,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93063",
    "latitude": 34.2727291,
    "longitude": -118.692634,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "96150",
    "latitude": 38.9146887,
    "longitude": -120.003094,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94080",
    "latitude": 37.642017,
    "longitude": -122.4260163,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92881",
    "latitude": 33.8503989,
    "longitude": -117.5509095,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91977",
    "latitude": 32.7126719,
    "longitude": -117.0109029,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90680",
    "latitude": 33.8020329,
    "longitude": -118.0096585,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95210",
    "latitude": 38.0198315,
    "longitude": -121.3226346,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95205",
    "latitude": 37.9572889,
    "longitude": -121.2729902,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94087",
    "latitude": 37.3533862,
    "longitude": -122.0514724,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92592",
    "latitude": 33.4934243,
    "longitude": -117.1488156,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90502",
    "latitude": 33.8332341,
    "longitude": -118.2899638,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90505",
    "latitude": 33.7942536,
    "longitude": -118.3341912,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90504",
    "latitude": 33.8718461,
    "longitude": -118.3256477,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92679",
    "latitude": 33.6477817,
    "longitude": -117.5760903,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91042",
    "latitude": 34.2462676,
    "longitude": -118.27468,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93274",
    "latitude": 36.2239195,
    "longitude": -119.3322037,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "95380",
    "latitude": 37.4982058,
    "longitude": -120.8505528,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92780",
    "latitude": 33.7469812,
    "longitude": -117.810169,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94587",
    "latitude": 37.6017832,
    "longitude": -122.0682482,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91786",
    "latitude": 34.1076375,
    "longitude": -117.668327,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91355",
    "latitude": 34.4422766,
    "longitude": -118.576809,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "94589",
    "latitude": 38.1280232,
    "longitude": -122.2566082,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90291",
    "latitude": 34.0005057,
    "longitude": -118.4642277,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93003",
    "latitude": 34.2732392,
    "longitude": -119.2596276,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93004",
    "latitude": 34.2798545,
    "longitude": -119.1911964,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93291",
    "latitude": 36.3314216,
    "longitude": -119.2984857,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "93277",
    "latitude": 36.2997507,
    "longitude": -119.3113309,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92083",
    "latitude": 33.1890153,
    "longitude": -117.2809708,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91201",
    "latitude": 34.174665,
    "longitude": -118.2923314,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90046",
    "latitude": 34.0905105,
    "longitude": -118.3501665,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90025",
    "latitude": 34.039804,
    "longitude": -118.4644063,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90034",
    "latitude": 34.0221004,
    "longitude": -118.4018018,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91362",
    "latitude": 34.1537821,
    "longitude": -118.7945823,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90604",
    "latitude": 33.9355773,
    "longitude": -118.010004,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "90602",
    "latitude": 33.9667798,
    "longitude": -118.0367443,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91306",
    "latitude": 34.2020039,
    "longitude": -118.5785491,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "91364",
    "latitude": 34.1678592,
    "longitude": -118.6201888,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "92887",
    "latitude": 33.8775712,
    "longitude": -117.7524899,
    "show_on_map": True
  },
  {
    "retailer": "Smart & Final",
    "retailer_key": "smart_final",
    "zip_code": "85364",
    "latitude": 32.6993254,
    "longitude": -114.6184326,
    "show_on_map": True
  }
]

print(f"Importing {len(rows)} Smart & Final stores...")
sb.table("store_locations").delete().eq("retailer_key", "smart_final").execute()
print("Deleted old Smart & Final entries")

# Deduplicate by zip_code since there's a unique constraint on retailer_key+zip_code
seen_zips = set()
deduped = []
for row in rows:
    if row['zip_code'] not in seen_zips:
        seen_zips.add(row['zip_code'])
        deduped.append(row)

print(f"After dedup by zip: {len(deduped)} stores")

for i in range(0, len(deduped), 250):
    batch = deduped[i:i+250]
    sb.table("store_locations").insert(batch).execute()
    print(f"Inserted batch {i//250 + 1}")

print("Done.")