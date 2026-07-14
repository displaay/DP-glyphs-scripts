# MenuTitle: Capital Words
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Opens one capitalized word for every alphabet letter in the current Edit tab, or
in a new tab if no Edit tab is open. Each letter has 100 embedded variants.
"""

import random
import string
import os
import sys

from GlyphsApp import Glyphs, Message

try:
	SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
	if SCRIPT_DIR not in sys.path:
		sys.path.insert(0, SCRIPT_DIR)
except Exception:
	pass

from _stylistic_variants import text_with_stylistic_variants


SCRIPT_NAME = "Capital Words"

EMBEDDED_WORDS = """
A Able About Above Actor After Again Agile Album Alert Alive Amber Anchor Animal Answer Apple Arena Artist Atlas Autumn Avenue Awake Acrawl Adarme Anemia Ameiva Aorist Amnion Ailing Afenil Akoasm Amusee Ablude Aeacus Aegean Amlong Aonach Aborad Accost Abdiel Adamas Aeried Alpine Acacin Albian Anusim Abound Andean Acoria Ababua Agawam Adital Aghast Alnein Acnida Andian Adonia Anotto Angela Alnico Agamae Anglic Amelia Adoral Actify Allies Amylan Abroad Acumen Amania Adread Ancile Adsorb Annale Andrea Abrook Alexin Amober Adolph Aiming Amyris Adrift Alalus Alraun Agroan Alogia Aecium Anaxon Accent Agazed Alpaca Apatan Acoine Anselm Apedom Abraid Alicia Alpieu Apache Amidin Ampery
B Baby Baker Balance Banana Banner Basic Beach Beauty Before Begin Better Beyond Bicycle Bitter Black Blue Book Border Brave Bright Brother Button Besoot Bayman Battik Bladed Bedway Bibble Bejade Baleen Babbie Besuit Balita Befume Bleeze Barton Behint Bakula Bedpan Baraca Batman Bewall Beglue Betask Baobab Bingle Bewest Basely Babism Bertat Begild Bayeta Basalt Baetyl Begluc Bisect Barolo Balder Belton Bahama Bacaba Beluga Bistro Birdie Beshag Behest Bjorne Balawu Basoko Bigeye Beclog Blenny Barong Birler Barret Baiter Baccae Beveil Blader Basuto Bembex Badaga Blamer Barway Bagwyn Baruch Barrow Basker Bandog Baluch Bemoon Benumb Beldam Blarny Bancal Befret Bireme Bertha Berapt Beseen
C Cabin Cable Camera Candy Capital Carbon Carry Castle Center Chance Change Cherry Circle City Clear Clever Clock Cloud Color Copper Cotton Chelem Cavort Cativo Caduca Clench Cimbia Choker Chawer Caller Chocho Clutch Cinene Chozar Carrel Celite Capuan Cither Cherem Canuck Chevon Chivey Causal Causer Chiral Clumse Cammed Clonal Carboy Clergy Cabaho Cashel Coated Ceylon Chroma Cactus Chymic Cervid Cleeky Caries Clifty Cheson Cakile Cental Cobalt Casate Clotho Cellae Cabuya Chinol Cerule Clumpy Cerris Cecity Chupon Childe Cardia Chuter Choric Cibola Chende Cletch Cerate Calean Chetty Chlore Clover Cagmag Cachou Cereal Chrome Camass Capias Chorea Classy Chogak Champy Cascol Chueta Climax
D Daily Dance Danger Daring Decade Decide Degree Desert Design Detail Dinner Direct Doctor Dollar Double Dream Driver During Dusty Dynamic Druith Dhauri Duster Dapple Dargue Degged Dhaura Densen Doddle Dither Drawly Dirhem Deltic Daunch Deftly Darzee Dizain Duplet Darnel Deceit Deemie Druery Dogtie Denary Demast Dutied Dosage Depart Dialin Diodia Dharma Decant Docile Dipody Dalton Disbar Debosh Dudler Didder Daimon Drawee Discus Dardan Dauber Diarch Divest Depute Doodle Decare Durani Devour Dinder Downer Doucet Dukery Diesel Docmac Diketo Dautie Daboia Decode Dorlot Desire Dittay Dagmar Deduce Derust Damson Damask Divata Dicast Durgan Dalles Dorter Deicer Doater Donary Dermal Dingly Danner
E Eager Early Earth Easy Edge Effect Effort Eight Either Elder Electric Energy Engine Enough Equal Evening Every Exact Extra Edict Evince Eleatic Ethine Eloise Eyeish Ensuer Earle Easier Echinid Empall Enmass Enrage Edictal Essoin Eaglet Elamite Egence Ectasis Eciton Easting Egypt Encore Espier Eyalet Etamin Elemin Ehretia Enaena Enfoil Embank Essang Egest Exsect Electly Estray Ethrog Encurl Earshot Ethane Earnest Encode Earnie Esteem Embden Enfoul Espial Endure Edenic Eponym Eater Emoloa Evoker Educt Eject Earmark Earpick Entail Ectally Escoba Entity Ebonite Evejar Eatable Enfile Elatcha Edgeman Elohim Erical Europa Eleidin Ectozoa Enleaf Erased Esopus Elbowed Embryo Enukki Eclegma Ellops Erudit
F Fabric Factor Family Famous Farmer Father Fellow Field Figure Final Finder Flower Focus Forest Formal Forward Fresh Friday Future Forane Finity Fertil Formin Funded Favism Fasting Fulham Folder Formee Fidele Furred Furoic Falsism Firmer Fumage Froise Flaggy Fretum Figaro Fester Firkin Fimble Faciend Factum Fearer Fandom Flaunt Facular Farleu Fetlow Faunal Freath Furrow Fundal Famulus Fenrir Forbit Fanwork Feared Fulgur Fustic Fantod Fonted Firmly Fathmur Forger Fretty Fabella Falsary Fracas Forthy Fairm Fodgel Former Fegary Filthy Foeish Fumago Fagot Faluns Figent Filing Freyja Faroese Fisted Fixate Frayed Fixing Floppy Fangle Faggery Feasor Fagoter Filter Fonduk Forged Ferula Fillip Fabled Funnel
G Garden Gentle Giant Gift Glass Golden Good Graceful Grain Grand Green Ground Group Guide Guitar Global Growing Ghaist Godful Gunite Greave Glummy Gurges Guttus Glacis Giftie Galuth Glover Gosain Granny Grapta Gentes Gally Glycyl Graben Gourdy Gruffy Gruffs Goffle Growth Gluten Glossy Grovel Gambet Gauger Gyrous Gummed Gurrah Galega Gerefa Gathic Gemmae Geonim Graven Gorbal Guffer Groser Gonial Goniac Gesten Gummer Gowpen Gynura Gyrant Gowked Galanas Galchic Gunate Gadling Gander Gratis Glumal Gyrate Girder Galey Gentry Garava Giglet Gubbin Glumpy Galop Galumph Grayly Gelong Gallet Gunebo Gunnar Gaduin Galline Grough Glider Goanna Gerald Gangue Gabby Gollar Grundy Guimpe Garage Goetae
H Habit Happy Harbor Honest Honey Hotel House Human Humble Hundred Hungry Hunter Hybrid Hidden Holiday Heavy History Hammock Hooded Hydroa Hummel Haire Haddock Hackery Harry Height Harshen Hummer Halfman Hester Helmed Hydrol Hexose Hazily Hallah Hatrack Habutai Hooped Hydria Havage Homely Hinney Hallex Hilary Henter Hustle Hearer Hipple Hatch Haunty Hardy Haircut Halcyon Heaver Haycap Hastler Hamus Howish Hallux Hitter Hippic Harmost Hairy Halfway Hearth Humbly Haunch Humify Hogget Honker Hunger Hurler Harsh Hardim Hornie Haffet Hockey Haggish Hebrew Husked Hitchy Hiatus Hammer Hygric Hiller Halyard Hotter Halting Hamza Hagride Happen Habile Haggis Hastati Heptyl Haglin Helmet Handbag Hazard Housal
I Ideal Image Impact Inch Income Index Infant Inside Island Item Ivory Issue Invite Iron Instant Indoor Input Inward Idoist Implial Ichthus Injurer Icteric Ibycus Inroad Impute Impling Inclip Ideate Inflood Icefish Incrash Induna Impubic Infamy Initive Inchpin Izzard Ingulf Indigo Inmeats Inport Imperia Immew Intine Indies Isabel Insorb Iambist Idaho Impulse Imbiber Impasse Incudes Igneous Isinai Icarian Idite Incuse Ionone Ingram Ignorer Inured Insect Idalia Inhere Ineri Indexer Ingress Inflow Indoles Inneity Ironly Injunct Inwrap Immure Impious Imitant Import Injured Isuret Inocyte Italic Illocal Ikhwan Ingle Infand Inkpot Invent Ileon Icily Ionium Imager Inwrit Inflame Incisor Infula Imban Indicia Ignatia
J Jacket Jagged Jazz Jewel Joined Journey Judge Juice Jumper Junior Jungle Justice Joyful Joking Journal Jackman Jacko Jean Jungli Jimmy Jewelry Jonque Jessie Jewling Jamesian Jovite Jelloid Jowari Jereed Joseite Jauntie Jyngine Jadeship Jodelr Jolter Jacchus Jawbone Jinjili Jarvey Jinglet Jacamar Jargon Jeanne Joloano Jollier Japygoid Justina Jwahar Jovial Jasmined Jemima Jowlop Joyant Jobarbe Jiggly Jamboree Jerry Jamie Jussion Jeerer Javelin Johnnie Joanna Janus Jervine Jamwood Jugerum Juliet Joint Johnny Jagath Jochen Jagua Janua Jobman Jowter Jocular Jailage Junto Jitney Jealousy Jayesh Jargonal Jarfly Jingled Jennet Jokist Janice Julien Jiffy Jawab Jumana Jady Jarvis Junius Jerkish Jukebox Jigget Justify Jacate
K Keeper Kettle Keyboard Kind Kitchen Kitten Knife Knock Known Kingdom Kindly Kinetic Kenai Kluxer Khalifa Kinkhab Karri Khaja Keelage Khila Kookri Kebbuck Kaross Kanagi Kobong Kabaya Kitab Khotana Ketosis Ketty Kidling Kerria Kokoon Kuruba Kosong Keeling Kikongo Ketipic Klafter Karagan Kekchi Khaiki Kaliana Knopite Khediva Kenaf Kleptic Kisra Kempy Kafirin Klanism Kebbie Keresan Katrine Kirking Kelchin Kaldani Kitish Kikuel Kinkly Kneeler Kobird Knurly Klaxon Kadayan Kinglet Kanten Kerchoo Kawika Klaus Kilerg Kinkled Korona Kajawah Kinsman Kashga Kharwar Karma Krigia Keita Khond Katik Kefir Karbi Khanda Keten Kanauji Kosher Knyazi Kipage Karaka Kraken Khubber Koulan Kickoff Kilah Khami Kiddy Kiloton Kickee
L Label Ladder Lady Large Later Laugh Layer Leader Learn Lemon Letter Light Likely Little Lively Local Loyal Lucky Lapsed Lasset Lagting Loreal Levite Labium Loaner Larvae Latris Limbed Labrus Lenten Lyrism Lactuca Lonhyn Lalland Lambkin Lentor Latona Laden Ladify Lugged Ladkin Ligate Lablab Lipped Loined Llautu Lowboy Lipoma Libral Lizard Layout Lokiec Limbie Lemnad Leucon Lushei Ledger Lenvoy Loggat Ledged Liyuan Lastre Lager Latten Lusory Libate Lagan Lender Lutrin Luteal Lisper Loathe Lechwe Lesche Lunger Libbra Laputa Loggia Licorn Liming Leglen Lorica Lilied Ludlow Lacunae Laking Loimic Libber Laager Launce Ladydom Laughy Ligula Lobber Lumine Litten Labroid Lowdah Lacis Lyrist
M Machine Magic Major Maker Market Matter Meadow Memory Method Middle Modern Moment Money Morning Mother Motion Mountain Music Mutual Meebos Medusa Madder Morkin Mucker Mohawk Morbid Mapach Merton Madman Mothed Mirage Malati Madiga Morgue Mizzle Mooner Mastax Mantle Mulley Modius Modify Majlis Mukluk Mazuma Mocker Mataco Mosque Machin Mowcht Micher Melder Mayhem Milchy Meloid Midtap Muffle Milsie Magnus Markka Moolet Mechir Mantic Mackle Magged Martha Morula Mating Measle Mizpah Mumble Moloid Mickle Milium Midday Mariou Missal Medium Monoid Messet Merely Minion Meeter Mistry Marmit Morong Module Milner Muffed Manism Moaria Marree Meccan Maggot Mitten Misled Moiler Maysin Markeb Milden Mnioid
N Narrow Nation Native Natural Nearby Needle Nerve Never Nickel Night Noble Normal North Notice Number Nurse Nutmeg Needer Nathe Neddy Nalita Nervine Nanda Nasab Nahani Naphtha Niblike Nasard Nectar Nyctea Neumic Nimble Nagual Netsman Napping Nodule Newborn Nayarit Nucula Nobble Naive Nailery Nictate Nonoic Nettion Notary Nonpar Novcic Nankin Nifle Napron Nipmuc Nicaean Neogamy Nagster Nigel Naggy Nasutus Nayaur Naght Nestler Nominy Nabby Needily Nidulus Nither Nasial Needler Nudist Narras Neptune Nigori Nippily Nooked Nester Nosema Novelty Nasiei Neigh Nitric Network Nonfat Neeld Nidor Netted Neuter Nidgety Naiad Nearly Nights Nickey Nubbly Ngaio Nuance Neuric Nonion Nurhag Neback Nandi Natter
O Object Ocean Office Olive Open Orange Order Origin Outside Oval Owner Oxygen Onward Option Orbit Oestrid Opelet Ogrism Oleate Ogrish Oathlet Oillike Opercle Oolak Ophioid Omaha Obclude Owlism Olycook Osmose Ooblast Oxygas Oppugn Oporto Opaque Opium Oreman Okapia Ooecial Oakweb Outsum Outhit Opinion Officer Onside Orchil Oarhole Offtype Outsay Outsee Oddment Ophitic Oxacid Omasum Onetime Outfly Ooscopy Onanist Outpop Oscine Oakesia Octodon Oophore Oxeate Olfacty Oncetta Oncosis Oozooid Oxidic Oleous Offish Onerary Ophrys Ovated Octoic Ononis Oogone Oarlike Octoid Onery Oroide Ocrea Obelus Odious Outgun Oestrum Onlook Octoad Oilhole Orchat Omnific Oilcup Orphic Ovenly Observe Onefold Ochroid Octavia Orphan Oophyte
P Paper Parent Park Partner Party Pattern People Perfect Piano Picture Planet Plenty Pocket Poetry Point Power Pretty Public Purple Phecda Pavane Poachy Parchy Papist Panung Patina Paroli Perten Palmae Parrel Picrol Phylon Picric Parlay Pollen Ponent Pastel Pinion Parley Polyad Picnic Picaro Plushy Plater Pentad Pimpla Pollam Penide Plucky Pilary Piking Pickup Penang Ploima Patine Pelmet Paynim Phenol Pamper Poiana Panful Podeon Palish Pennet Pistil Penaea Paulin Papyri Panaka Persea Petune Pawnor Poales Phasic Pistia Piffle Podial Peewee Pawner Pituri Phiale Papane Peglet Paring Period Poller Pilous Peltry Planer Petaly Piegan Pensum Pamiri Pomace Pataca Pauper Polish Papion Pinker Penult
Q Quality Quarter Queen Query Quick Quiet Quilt Quiver Quote Quorum Quaint Quantum Quest Question Queenright Quirksey Quotiety Quipu Quietsome Quisby Querecho Quillaic Quernal Querendi Queencraft Quarl Quietism Quaily Quoined Questful Quila Quinite Queenship Quoin Quilting Quirkish Quale Quid Quinonyl Quotation Quinism Quintuple Quickener Quickhatch Quisling Quenchable Quinch Quintadena Quotidian Quaintise Quaffingly Qere Quinolinic Quail Quippy Quantify Quadruped Quinsywort Quei Quizzable Quinic Quadriceps Queendom Quirl Quiles Quiniretin Quipsome Quinaielt Quamoclit Quadratics Quaver Quimbaya Quileute Quartine Quanta Queue Quieten Quinoline Quadricorn Quinonic Quaestor Quatorzain Qualify Queme Quernstone Quadrille Quadric Querulent Quemefully Quoddity Quixotism Quotennial Quintette Queer Quinsied Quadrireme Quinovose Quondam Quirites Quartan
R Radio Raise Range Rapid Reader Really Reason Record Red River Road Rocket Rough Round Royal Rubber Runner Rhythm Ramper Raving Rignum Risser Rameal Rinner Riancy Rinker Ranked Rekiss Reeper Renvoi Relais Redeem Relast Raunge Reveil Raster Ramsey Resink Reduct Rasion Rashti Recess Recopy Raucid Rigsby Reeker Retalk Rifian Rather Revert Regrow Reseda Recoup Revary Repage Raping Regill Retomb Rester Ribhus Rakhal Reline Renvoy Rarity Remask Richen Remiss Rictal Rasper Raioid Ramist Rebato Regift Retted Ratoon Refire Resaca Rackle Resume Raglin Reheal Rivage Reseam Render Reenge Ramate Repent Repale Rapine Ribber Riddam Raider Regime Rerail Rifler Resnub Retort Regret Razzia Rerise
S Safety Sample School Science Season Second Secret Shadow Shape Silver Simple Sister Skill Sky Smart Smooth Sound Spring Square Story Sedged Shawny Scride Seaway Sarraf Screak Scrine Samsam Sibbed Saloon Samish Sergiu Sidney Seljuk Saying Sundial Setter Sesban Scatch Scarce Schout Seenie Shaped Scutal Scarth Scavel Sicker Scarer Sabeca Salute Shiest Sadism Sextry Shaker Silvia Scouse Secohm Scarus Sequin Shavee Salmis Shower Satrae Sejant Shorer Senate Seller Sapful Sacope Schism Silker Sickly Sailed Sherry Scarry Sacken Scious Sandan Senusi Semmet Scopet Scolia Seamed Sanjib Shippo Sertum Sagene Samian Scroop Sangha Sawish Seiche Shelfy Selena Scuffy Saccha Satron Scilla Settee Saltee
T Table Talent Target Taste Teacher Tennis Theory Thirty Ticket Time Tiny Today Tomato Total Travel Tree True Tunnel Taheen Tapper Taxeme Tatchy Terton Thulia Theist Taisch Titter Tenant Throne Tinned Tineal Tappet Thuban Tecuna Topper Titbit Thrack Tettix Thusly Tivoli Totara Toozoo Topass Teopan Tanach Tandem Teller Tackey Tipple Teaism Tandle Thrush Tenent Tectal Tilley Tiptop Thecla Tagala Thinly Talmud Tongan Tabard Teacup Taruma Themis Tabula Tomkin Tiffle Tactus Tinguy Tinder Tigger Tcheka Tankah Teevee Tawdry Terret Tiplet Thetic Theres Thesis Taluto Tested Tipper Tahsil Thakur Tamber Tippee Tonjon Tecoma Tibbie Tegean Toetoe Thermo Teerer Topepo Tonger Tombic Tilpah Taking
U Uncle Under Union Unique Unit Update Upper Useful Usual Utility Urban Urgent User Using Universal Unempt Untall Unhang Upknit Ungild Unfile Undies Unshop Unbarb Ussels Upplow Uranyl Uluhi Unwary Upfeed Unstop Unworn Upmove Unspun Unturf Upstir Ulema Ungird Uphold Upping Uncoat Uphurl Upcock Upyoke Uptilt Uncoly Unsped Unbred Unrule Ubiquit Uncall Upjerk Unkiss Unstep Unhigh Unloop Unfain Ulmaria Ungear Unsort Unride Upwent Unburn Uracil Ulnar Ungaro Uppish Unsole Uprive Uncoil Umpqua Unware Unused Unbark Unsewn Utopia Undate Uranic Unclay Untrod Untrig Updart Ululant Unkist Uhtsong Unguis Unwarm Uroxin Uphand Unesco Unslow Ulling Unepic Unleaf Unglad Undoer Unroll Unsing Unvest Ulminic
V Valley Value Velvet Vendor Verbal Verify Vessel Victory Video Village Violet Virtue Visible Vision Visual Volume Voyage Vastate Visitee Vilify Veridic Vaunted Verek Variag Verdoy Vicki Violina Verbose Varlet Venust Virtual Vallary Vesture Vaivode Vingolf Veinlet Veily Vernier Vacona Vendace Vertigo Venture Viver Velte Vittate Verminy Venue Vesicae Valetry Verge Volumed Virole Verbena Velary Vagal Vacoua Vespoid Vakass Viscid Vizard Voglite Vacatur Valois Virgin Vilhelm Vapor Vihuela Vateria Voluspa Viner Versant Votish Vervet Vaalite Vedism Volsci Vacuome Vehicle Visne Vintner Voicer Valeria Vastily Vitamer Vastity Vivek Vanfoss Verdant Vaginal Vodka Virago Voidly Valvata Valvate Viduate Vives Vidya Vitrean Vectis Vatter
W Wagon Waiter Water Weather Weekly Welcome Western White Window Winter Wisdom Wonder Wooden Worker World Writer Washy Waganda Waxlike Washman Worder Wavably Warrin Warori Warday Worble Waspily Warty Wayless Wanly Warse Wanty Wamefou Wharve Warless Wished Winful Wholly Weedy Waved Wanle Waybook Wagsome Woolwa Walling Weesh Warmer Watala Warmly Wallman Wavery Wollop Waddent Whiten Wefted Wissel Wuther Whally Waxbush Waygang Webwork Wicken Wowser Wellat Whekau Waymark Worded Woodly Weigela Wurset Wetted Weepy Wallaby Wavicle Wassie Worthy Wearish Waggle Waguha Wilkin Walpapi Wealden Whatna Weedish Weeps Wrecky Warnoth Wieldy Wedging Wadna Webber Waken Wearily Waybung Wimick Wauner Woofer Wizzen Wochua Winger
X Xenon Xeric Xylem Xylene Xylophone Xiphoid Xenial Xanthic Xmas Xenolith Xiphosura Xyridaceae Xerus Xenicus Xeromenia Xanthosoma Xylotomous Xylon Xosa Xerotes Xylonic Xenophobe Xiphias Xiphosuran Xenosaurid Xyst Xiphosure Xerotherm Xenophora Xenotime Xylenyl Xyridales Xyster Xenophobia Xeromorphy Xanthamic Xylitol Xylosma Xiphodynia Xenopodid Xiphiid Xylotile Xerophytic Xanthian Xanthisma Xenogenous Xylophagid Xyla Xerography Xanthyl Xysti Xenagogy Xerodermia Xiphisura Xerasia Xyrid Xylol Xylometer Xanthone Xerotic Xiphius Xenomi Xiphura Xema Xanthoma Xenelasy Xanthate Xenoblast Xeriff Xanthoura Xylorcinol Xerostomia Xylotomist Xylonite Xina Xenian Xyloidin Xylina Xenium Xiphiidae Xylylene Xenelasia Xenarthral Xoana Xanthopia Xenophile Xenopus Xenolite Xiraxara Xenocryst Xerotocia Xenicidae Xyloid Xenos Xylotomy Xanthin Xerogel Xenopeltid Xanthomata Xylomancy
Y Yard Yearly Yellow Yesterday Yield Young Youth Yummy Yoga Yogurt Yonder Yahooish Yeuk Yock Yurt Yetlin Yirth Yearling Yeta Yukaghir Yawl Yelmer Yoretime Yokuts Youff Yakan Yuruk Yeoman Yolked Youthy Yameo Yakut Yamilke Youp Yokemating Yerk Yearbird Yttrium Yeard Yodeler Yacht Yeowoman Yuck Yielding Yardstick Yegg Yuzlik Yond Yallow Youthless Yonside Yale Yawnups Yagger Yeomanlike Yarr Yogasana Yawp Yont Yugada Yardland Yabby Yeguita Yanky Yurta Yangtao Yachtdom Yomud Youthfully Yavapai Youthheid Yellowback Yakutat Yaffingale Yelloch Youthful Ypurinan Yponomeuta Yeel Yellowwort Yestern Yerava Yengeese Yukian Yander Yatalite Yirmilik Youl Yince Yoldia Yuckle Yamstchik Yoncopin Yezzy Yuapin Yeorling Year Yonderly Yellowcup Yirn
Z Zebra Zero Zipper Zodiac Zone Zoom Zealous Zenith Zesty Zinc Zigzag Zoilist Zarema Zyga Zwitterion Zenaida Zilla Zygadenus Zoologer Zachariah Zoogony Zulhijjah Zoomimetic Zamindar Zygotoid Zoehemera Zoogloeic Zeburro Zowie Zootomic Zoothecia Zerma Zeunerite Zayin Zygophore Zoophily Zircon Zenick Zoographer Zibetum Zigzaggy Zingel Zonite Zirconic Zealful Zincuret Zymogenic Zeuzeridae Zillion Zoogonic Zanclodon Zoocytial Zealotism Zygopteran Zooscopy Zebrass Zoodynamic Zoolite Zonar Zonal Zaqqum Zoistic Zoospermia Zoonomist Zygomata Zanclidae Zincograph Zoophilist Zygomycete Zoothecium Zande Zaniah Zincalo Zoochemy Zonation Zizyphus Zany Zestily Zenobia Zirkelite Zonally Zoolatrous Zakkeu Zythem Zeus Zonule Zygose Zanyish Zoocystic Zizz Zoned Zirconia Zygospore Zoonite Zyrian Zelkova Zachun Zoophyte Zeelander Zunyite
"""


def build_word_bank():
	word_bank = {}
	for raw_line in EMBEDDED_WORDS.splitlines():
		line = raw_line.strip()
		if not line:
			continue
		parts = line.split()
		letter = parts[0]
		words = parts[1:]
		if letter in string.ascii_uppercase:
			word_bank[letter] = words[:100]
	return word_bank


WORD_BANK = build_word_bank()


def current_tab(font):
	tab = getattr(font, "currentTab", None)
	if callable(tab):
		try:
			tab = tab()
		except Exception:
			tab = None
	return tab


def show_text(font, text):
	tab = current_tab(font)
	if tab is not None:
		try:
			tab.text = text
			return
		except Exception:
			pass
		try:
			tab.setText_(text)
			return
		except Exception:
			pass
	font.newTab(text)


def random_capital_words():
	words = []
	for letter in string.ascii_uppercase:
		letter_words = WORD_BANK.get(letter, [])
		if not letter_words:
			words.append(letter)
		else:
			words.append(random.choice(letter_words))
	return "%s\n%s" % (" ".join(words[:13]), " ".join(words[13:]))


def main():
	font = Glyphs.font
	if font is None:
		Message(title=SCRIPT_NAME, message="Open a font and run the script again.")
		return
	show_text(font, text_with_stylistic_variants(font, random_capital_words()))


main()
