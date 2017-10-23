import logging
import requests
from lxml import etree
from dalet import parse_date
from datetime import datetime

from libsanctions import Source, Entity, Alias, Identifier, make_uid
from libsanctions import BirthPlace, BirthDate
from libsanctions.util import remove_namespace

log = logging.getLogger(__name__)

SDN_XML = 'https://www.treasury.gov/ofac/downloads/sdn.xml'
NONSDN_XML = 'https://www.treasury.gov/ofac/downloads/consolidated/consolidated.xml'

ENTITY_TYPES = {
    'Individual': Entity.TYPE_INDIVIDUAL,
    'Entity': Entity.TYPE_ENTITY,
    'Vessel': Entity.TYPE_VESSEL,
    'Aircraft': None
}
ALIAS_QUALITY = {
    'strong': Alias.QUALITY_STRONG,
    'weak': Alias.QUALITY_WEAK
}
ID_TYPES = {
    'Passport': Identifier.TYPE_PASSPORT,
    'Additional Sanctions Information -': None,
    'US FEIN': Identifier.TYPE_OTHER,
    'SSN': Identifier.TYPE_OTHER,
    'Cedula No.': Identifier.TYPE_NATIONALID,
    'NIT #': Identifier.TYPE_NATIONALID,
}


def parse_entry(source, entry, url, updated_at):
    uid = entry.findtext('uid')
    type_ = ENTITY_TYPES[entry.findtext('./sdnType')]
    if type_ is None:
        return
    entity = source.create_entity(make_uid(url, uid))
    entity.type = type_
    entity.updated_at = updated_at
    programs = [p.text for p in entry.findall('./programList/program')]
    entity.program = '; '.join(programs)
    entity.summary = entry.findtext('./remarks')
    entity.function = entry.findtext('./title')
    entity.first_name = entry.findtext('./firstName')
    entity.last_name = entry.findtext('./lastName')

    for aka in entry.findall('./akaList/aka'):
        alias = entity.create_alias()
        alias.first_name = aka.findtext('./firstName')
        alias.last_name = aka.findtext('./lastName')
        alias.type = aka.findtext('./type')
        alias.quality = ALIAS_QUALITY[aka.findtext('./category')]

    for ident in entry.findall('./idList/id'):
        type_ = ID_TYPES.get(ident.findtext('./idType'), Identifier.TYPE_OTHER)
        if type_ is None:
            continue
        identifier = entity.create_identifier()
        identifier.type = type_
        identifier.number = ident.findtext('./idNumber')
        identifier.country = ident.findtext('./idCountry')
        identifier.description = ident.findtext('./idType')

    for addr in entry.findall('./addressList/address'):
        address = entity.create_address()
        address.street = addr.findtext('./address1')
        address.street_2 = addr.findtext('./address2')
        address.city = addr.findtext('./city')
        address.country = addr.findtext('./country')

    for pob in entry.findall('./placeOfBirthList/placeOfBirthItem'):
        birth_place = entity.create_birth_place()
        birth_place.place = pob.findtext('./placeOfBirth')
        birth_place.quality = BirthPlace.QUALITY_WEAK
        if pob.findtext('./mainEntry') == 'true':
            birth_place.quality = BirthPlace.QUALITY_STRONG

    for pob in entry.findall('./dateOfBirthList/dateOfBirthItem'):
        birth_date = entity.create_birth_date()
        birth_date.date = parse_date(pob.findtext('./dateOfBirth'))
        birth_date.quality = BirthDate.QUALITY_WEAK
        if pob.findtext('./mainEntry') == 'true':
            birth_date.quality = BirthDate.QUALITY_STRONG

    entity.save()


def ofac_parse(xmlfile):
    source = Source('us-ofac')
    for url in (SDN_XML, NONSDN_XML):
        res = requests.get(url, stream=True)
        doc = etree.parse(res.raw)
        remove_namespace(doc, 'http://tempuri.org/sdnList.xsd')

        updated_at = doc.findtext('.//Publish_Date')
        updated_at = datetime.strptime(updated_at, '%m/%d/%Y')

        for entry in doc.findall('.//sdnEntry'):
            parse_entry(source, entry, url, updated_at)

    source.finish()


if __name__ == '__main__':
    ofac_parse('us-ofac-sdn')
