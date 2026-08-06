# MenuTitle: Czech text
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Opens random Czech proofing text in the current Edit tab, or in a new tab if
no Edit tab is open. Each sample includes varied Czech text for quick text
testing.
"""

import random

from GlyphsApp import Glyphs, Message


SCRIPT_NAME = "Czech text"
DEFAULTS_KEY = "com.displaay.testing.CzechText.lastIndex"

OPENERS = [
	"Po klidném ránu redaktorka připravila dlouhou poznámku pro celé oddělení",
	"Než začala čtvrteční porada, šest kolegů tiše srovnalo židle u stolu",
	"Během jarního trhu prodával pekař křupavé rohlíky vedle staré radnice",
	"Každý zkušený grafik zkontroloval sazbu ještě před poslední korekturou",
	"Z horního balkonu si návštěvníci všimli šedé oblohy a rušné třídy",
	"V úzkém ateliéru tiše hučela tiskárna a čerstvé nátisky ležely na stole",
	"Kousek za nádražím visel výrazný plakát, který zval lidi do zahrady",
	"Mnoho poctivých řemeslníků dorazilo brzy s krabicemi, sešity a kávou",
	"V úterý večer poslala místní autorka živý sloupek do městských novin",
	"Potichu mladý archivář označil složky, deníky, lístky a staré mapy",
	"Několik hudebníků ladilo žestě, dřevo a struny před večerní zkouškou",
	"Odvážný pilot sledoval zlatý obzor nad mraky a prázdnými poli",
	"Pod skleněnou střechou lidé porovnávali barvy, váhy, ceny a termíny",
	"S přesným načasováním hostitel přivítal každého hosta a odpověděl na dotazy",
	"Včera muzeum otevřelo komorní výstavu o strojích, paměti a řemesle",
	"Přátelská soudkyně vysvětlila pravidlo a potom vyzvala oba týmy k pokračování",
	"Protože byl sál plný, objevily se další židle podél boční zdi",
	"Klidné hlasy zaplnily místnost, zatímco modrý zápisník putoval z ruky do ruky",
	"Dole v kavárně podávali pomerančový koláč, černý čaj a perlivou vodu",
	"Každý víkend přecházely rodiny přes náměstí do knihovny a malého kina",
]

MIDDLES = [
	"Čísla 12, 48 a 305 byla zakroužkovaná červenou tužkou",
	"Někdo se zeptal: „Přijde finální podklad ještě před šestou hodinou?“",
	"Odpověď byla jednoduchá: upravit, porovnat, vytisknout a znovu přečíst",
	"Krátká poznámka říkala: „Nechte okraje klidné, ale dejte prostor popiskům“",
	"Nadpis pracoval s verzálkami, minusky, číslicemi a ostrou interpunkcí",
	"Druhý odstavec prověřil čárky, tečky, uvozovky i otazníky",
	"Ukázka obsahovala slova jako žluťoučký, kůň, příliš, ďábel a řeka",
	"Korektury putovaly od stolu ke stolu a každý označil jeden nebo dva detaily",
	"Poslední stránka potřebovala rovnováhu, rytmus, texturu a trochu trpělivosti",
	"Faktura uváděla částku 24,50 Kč, slevu 18 % a kód AX-719",
	"Vedle sebe se objevila jména Anežka, Čestmír, Řehoř, Šárka a Žofie",
	"Místnost ztichla, když z tiskárny vyjel první čistý nátisk",
	"Starý nápis hlásal: Otevřeno denně, za deště i za jasného počasí",
	"Rozvržení se znovu změnilo, ale sdělení zůstalo jasné a použitelné",
	"Každý řádek míchal úzké tvary, kulatá písmena, háčky a dlouhé tahy",
	"Návštěvník napsal poznámku na stránku 7, odstavec 3, řádek 12",
	"Pečlivá korektura dokáže ukázat barvu, rytmus, proklad i mezery najednou",
	"Čerstvý papír, tmavý inkoust a pozorné oči udělaly velký rozdíl",
	"Tým kontroloval e-maily, štítky, popisky, nabídky a drobný text",
	"I nejkratší česká slova pomohla odhalit těsné spoje a neklidné mezery",
]

DETAILS = [
	"protože stránka potřebovala vyrovnanou texturu v několika různých velikostech",
	"zatímco tým porovnával tmavá místa, otevřené vnitřky a volné mezery",
	"aby ukázka prozradila, jak se běžná čeština chová v delším odstavci",
	"když se odpolední světlo pomalu měnilo na stole i v poznámkách",
	"než někdo rozhodl, které drobné opravy opravdu stojí za zachování",
	"i když první verze působila klidně už z pohodlné vzdálenosti",
	"protože úzká písmena, kulaté tvary a šikmé tahy vyžadovaly stejnou pozornost",
	"zatímco stejná věta byla čtena nahlas, označena a znovu zkontrolována",
	"aby každá změna mohla být posouzena uvnitř uvěřitelného textu",
	"když mezi známými slovy začaly vystupovat tiché, ale důležité detaily",
]

CLOSERS = [
	"Nakonec všichni korekturu schválili s rychlým úsměvem.",
	"Nic nepůsobilo uspěchaně a stránka zůstala příjemně čitelná.",
	"Další verze byla čistší, klidnější a jistější.",
	"Kolem poledne byla celá sada připravená na další pečlivý průchod.",
	"Takové obyčejné věty jsou užitečné, když má čeština dostat prostor.",
	"Výsledek působil vyváženě v širokých, úzkých, tmavých i světlých tvarech.",
	"Ještě jeden výtisk potvrdil, že změny stojí za ponechání.",
	"Ukázka zůstala dost prostá na to, aby nerušila samotné posuzování.",
	"Dobrý zkušební text má znít přirozeně, ne pouze mechanicky.",
	"Tento malý postup ušetřil týmu několik pozdních překvapení.",
	"Řádek po řádku byla textura klidnější a snáze čitelná.",
	"Dobré mezery dokázaly uklidnit celý odstavec v každé velikosti.",
	"I rychlá kontrola byla jasnější díky různým slovům a znaménkům.",
	"Práce skončila poznámkami na zítřek a úhlednou hromádkou papírů.",
	"Potom si redaktorka vybrala čaj, ticho a ještě jeden poslední pohled.",
	"Příběh byl jednoduchý, ale písmena měla dost práce.",
	"Na stránce se potkaly dříky, oblouky, háčky, čárky i spodní dotahy.",
	"Užitečný vzorek žádá po písmu řešení mnoha malých problémů.",
	"Nejlepší korektura je obyčejná natolik, aby ukázala neobyčejné detaily.",
	"Každé spuštění má nabídnout jiný hlas a trochu odlišnou texturu.",
]

ENDING_DETAILS = [
	"s dostatečnou délkou na odhalení mezer, které krátké ukázky často skryjí",
	"ale stále jako něco, co by člověk mohl opravdu číst",
	"a odstavec dal písmenům více prostoru usadit se do rytmu",
	"takže konečný dojem závisel na textu, ne na izolovaných znacích",
	"s interpunkcí a tvary slov přirozeně vloženými do věty",
	"a každý řádek nesl trochu jinou rovnováhu šířky a barvy",
	"zatímco korektura zůstala dost jednoduchá pro rychlé rozhodování",
	"aby čtenář mohl posoudit pohodlí, hustotu a tempo najednou",
	"a obyčejný jazyk usnadnil všimnout si neklidných detailů",
	"s delší větou, která dala písmu poctivější malou zátěž",
]


def build_text_variants():
	texts = []
	for index in range(100):
		opener = OPENERS[index % len(OPENERS)]
		middle = MIDDLES[(index * 7) % len(MIDDLES)]
		closer = CLOSERS[(index * 13) % len(CLOSERS)]
		second_middle = MIDDLES[(index * 11 + 3) % len(MIDDLES)]
		detail = DETAILS[(index * 5) % len(DETAILS)]
		ending_detail = ENDING_DETAILS[(index * 3) % len(ENDING_DETAILS)]
		title = "Ukázka %03i" % (index + 1)
		texts.append(
			"%s\n%s, %s. %s. %s. %s, %s."
			% (title, opener, detail, middle, second_middle, closer.rstrip("."), ending_detail)
		)
	return texts


TEXT_VARIANTS = build_text_variants()


def stored_last_index():
	try:
		return int(Glyphs.defaults[DEFAULTS_KEY])
	except Exception:
		return None


def store_last_index(index):
	try:
		Glyphs.defaults[DEFAULTS_KEY] = index
	except Exception:
		pass


def random_variant():
	indexes = list(range(len(TEXT_VARIANTS)))
	last_index = stored_last_index()
	if last_index in indexes and len(indexes) > 1:
		indexes.remove(last_index)
	index = random.choice(indexes)
	store_last_index(index)
	return TEXT_VARIANTS[index]


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


def main():
	font = Glyphs.font
	if font is None:
		Message(title=SCRIPT_NAME, message="Open a font and run the script again.")
		return
	show_text(font, random_variant())


main()
