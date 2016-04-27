# coding: utf-8
from grow.pods import pods
from grow.pods import storage
from grow.testing import testing
import unittest


class CatalogsTest(unittest.TestCase):

    def setUp(self):
        dir_path = testing.create_test_pod_dir()
        self.pod = pods.Pod(dir_path, storage=storage.FileStorage)
        self.pod.catalogs.compile()

    def test_list_locales(self):
        self.assertItemsEqual(
            ['de', 'fr', 'en', 'it', 'ja'],
            self.pod.catalogs.list_locales())

    def test_extract(self):
        template_catalog = self.pod.catalogs.extract()
        self.assertEqual(30, len(template_catalog))
        expected = [
            'Hello World!',
            'Hello World 2!',
            'Tagged String',
            'Tagged String in List 1',
            'Tagged String in List 2',
            'Tagged localized title.',
            'Tagged field in podspec',
            'string content tagged',
            'standalone string content tagged',
            'General body content',
            u'DE body content with ünicodé',
            'Global string',
            'Global string in HTML',
            'Global string in CSV',
            'CSV with blueprint locales',
            'Body content for blueprint locales',
            'YAML content for blueprint locales',
        ]
        for string in expected:
            self.assertIn(string, template_catalog)

        # Verify "include_obsolete" behavior.
        self.assertNotIn('foo', template_catalog)

        template_catalog.add('foo', 'bar')
        self.pod.catalogs.write_template(
            self.pod.catalogs.template_path, template_catalog)

        template_catalog = self.pod.catalogs.extract(include_obsolete=True)
        self.assertIn('foo', template_catalog)

        template_catalog = self.pod.catalogs.extract(include_obsolete=False)
        self.assertNotIn('foo', template_catalog)

        self.assertIn('string content tagged', template_catalog)
        self.assertNotIn('string content untagged', template_catalog)

    def test_localized_extract(self):
        self.pod.catalogs.extract(localized=True)

        # Pod locale (defined in podspec)
        fr_catalog = self.pod.catalogs.get('fr')
        # - from various contexts around the pod
        self.assertIn('Tagged localized title.', fr_catalog)
        self.assertIn('Tagged field in podspec', fr_catalog)
        self.assertIn('string content tagged', fr_catalog)
        self.assertIn('standalone string content tagged', fr_catalog)
        self.assertIn('General body content', fr_catalog)
        self.assertIn('Body content for blueprint locales', fr_catalog)
        self.assertIn('YAML content for blueprint locales', fr_catalog)
        self.assertIn('Global string', fr_catalog)
        self.assertIn('Global string in HTML', fr_catalog)
        self.assertIn('Global string in CSV', fr_catalog)
        # - from contexts which explicitly declare other locales (not fr)
        self.assertNotIn('Tagged localized body.', fr_catalog)

        # Another pod locale
        de_catalog = self.pod.catalogs.get('de')
        self.assertIn('AboutDE', de_catalog)
        self.assertIn(u'DE body content with ünicodé', de_catalog)

        # Non-pod locale (not defined in podspec)
        hi_catalog = self.pod.catalogs.get('hi_IN')
        # - from contexts which explicitly declare hi_IN
        self.assertIn('Tagged localized title.', hi_catalog)
        self.assertIn('Tagged localized body.', hi_catalog)

        # Current (potentially undesirable) behaviour:-

        # 1. Strings in locale-specific doc parts are extracted for all the
        #    doc's locales
        self.assertNotIn('AboutDE', fr_catalog)
        self.assertNotIn(u'DE body content with ünicodé', fr_catalog)

        # 2. Strings in various 'global' contexts are extracted for EVERY
        #    locale used ANYWHERE in the pod (not just those in podspec.yaml):
        # a. In podspec.yaml
        self.assertNotIn('Tagged field in podspec', hi_catalog)
        # b. In CSV files in /content/ or /data/
        self.assertNotIn('string content tagged', hi_catalog)
        self.assertNotIn('standalone string content tagged', hi_catalog)
        self.assertNotIn('CSV with blueprint locales', hi_catalog)
        # c. In /content/ without $localization defined in doc
        self.assertNotIn('Global string', hi_catalog)
        self.assertNotIn('Global string in HTML', hi_catalog)
        self.assertNotIn('Global string in CSV', hi_catalog)
        # d. ... even if locales are specified in the blueprint
        self.assertNotIn('Body content for blueprint locales', hi_catalog)
        self.assertNotIn('YAML content for blueprint locales', hi_catalog)

    def test_iter(self):
        locales = self.pod.catalogs.list_locales()
        for catalog in self.pod.catalogs:
            self.assertIn(str(catalog.locale), locales)

    def test_get(self):
        self.pod.catalogs.get('fr')

    def test_get_template(self):
        template = self.pod.catalogs.get_template()
        self.assertTrue(template.exists)
        template = self.pod.catalogs.get_template('messages.test.pot')
        self.assertFalse(template.exists)
        self.assertEqual(0, len(template))

    def test_compile(self):
        self.pod.catalogs.compile()

    def test_to_message(self):
        self.pod.catalogs.to_message()

    def test_init(self):
        self.pod.catalogs.init(['fr'])

    def test_update(self):
        self.pod.catalogs.update(['fr'])

    def test_filter(self):
        locales = ['de']
        catalogs = self.pod.catalogs.filter(
            out_path='./untranslated.po',
            locales=locales,
            localized=False)
        de_catalog = catalogs[0]
        self.assertEqual(3, len(de_catalog))

        paths = [
            '/content/pages/yaml_test.html',
        ]
        catalogs = self.pod.catalogs.filter(
            out_path='./untranslated.po',
            locales=locales,
            paths=paths,
            localized=False)
        de_catalog = catalogs[0]
        self.assertEqual(1, len(de_catalog))

    def test_filter_localized(self):
        locales = ['de', 'fr']
        catalogs = self.pod.catalogs.filter(
            out_dir='./untranslated/',
            locales=locales,
            localized=True)
        localized_de_catalog = catalogs[0]
        localized_fr_catalog = catalogs[1]
        fr_catalog = self.pod.catalogs.get('fr')
        self.assertEqual(3, len(localized_de_catalog))
        self.assertEqual(14, len(localized_fr_catalog))
        self.assertEqual(14, len(fr_catalog))

        paths = [
            '/content/pages/yaml_test.yaml',
            '/views/home.html',
        ]
        locales = ['de', 'fr']
        catalogs = self.pod.catalogs.filter(
            out_dir='./untranslated/',
            locales=locales,
            paths=paths,
            localized=True)
        localized_de_catalog = catalogs[0]
        localized_fr_catalog = catalogs[1]
        self.assertEqual(3, len(localized_de_catalog))
        self.assertEqual(14, len(localized_fr_catalog))


if __name__ == '__main__':
    unittest.main()
