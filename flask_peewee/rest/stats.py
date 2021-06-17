import csv
import io as StringIO
import pytz

from flask import request
from peewee import fn, R, ForeignKeyField, ReverseRelationDescriptor
from peewee import ProgrammingError, DataError
from playhouse.postgres_ext import ArrayField, JSONField

from . import RestResource


class StatsQueryBuilder(object):

    relationship = (ForeignKeyField, ReverseRelationDescriptor)

    aggregator_map = {
        "count": fn.Count,
        "sum": fn.Sum,
        "max": fn.Max,
        "min": fn.Min,
        "avg": fn.Avg,
        "distinct": lambda *args, **kwargs: fn.Count(fn.Distinct(*args, **kwargs))
    }

    def __init__(self, model):
        self.model = model
        self.joins = []
        self.aliases = []
        self.group_by_fields = []
        self.selected_fields = []
        self.selector = None

    @classmethod
    def parse_json_field(cls, fieldname):
        if "." in fieldname:
            fieldname, lookups = fieldname.split(".", 1)
            lookups = lookups.split(".")
        else:
            lookups = ()
        return fieldname, lookups

    def parse_field(self, fieldname):
        subjoins = []
        model_attr = self.model
        for piece in fieldname.split("__"):
            model_attr = getattr(model_attr, piece)
            if isinstance(model_attr, self.relationship):
                model_attr = model_attr.rel_model
                subjoins.append(model_attr)
        return model_attr, piece, subjoins

    def process_timefields(self, binsize, timefield, timezone):
        timefield_sql = R("t1.\"%s\" AT TIME ZONE '%s'" % (timefield, timezone))
        self.selector = fn.date_trunc(binsize, timefield_sql)
        self.group_by_fields.append(self.selector)
        self.selected_fields.append(self.selector.alias(timefield))

    def process_aggregator(self, aggregator, aggregate_fieldname):
        fieldname, lookups = self.parse_json_field(aggregate_fieldname)
        model_attr, piece, subjoins = self.parse_field(fieldname)
        alias = "%s_%s" % (aggregator.lower(), piece)
        self.joins.append(subjoins)
        agg = self.aggregator_map[aggregator.lower()]

        if isinstance(model_attr, JSONField):
            for lookup in lookups:
                model_attr = model_attr[lookup]
            if aggregator in ("Sum", "Max", "Min", "Avg"):
                model_attr = model_attr.cast("int")

            alias = '.'.join([alias] + lookups)
            self.selected_fields.append(agg(model_attr).alias('"%s"' % alias))
            self.aliases.append(alias)
        else:
            self.selected_fields.append(agg(model_attr).alias(alias))
            self.aliases.append(alias)

    def process_group_by(self, g):
        g, lookups = self.parse_json_field(g)
        model_attr, piece, subjoins = self.parse_field(g)
        self.joins.append(subjoins)

        if isinstance(model_attr, self.relationship):
            self.selected_fields.insert(0, model_attr.id.alias(piece))
            self.group_by_fields.insert(0, model_attr.id)
        elif isinstance(model_attr, ArrayField):
            self.selected_fields.insert(0, fn.unnest(model_attr).alias(piece))
            self.group_by_fields.insert(0, fn.unnest(model_attr))
        elif isinstance(model_attr, JSONField):
            for lookup in lookups:
                model_attr = model_attr[lookup]
            alias = '.'.join([piece] + lookups)
            self.selected_fields.insert(0, model_attr.alias('"%s"' % alias))
            self.group_by_fields.insert(0, model_attr)
        else:
            self.selected_fields.insert(0, model_attr)
            self.group_by_fields.insert(0, model_attr)

    def build(self):
        query = self.model.select(*self.selected_fields)

        joined = set()
        for subjoins in self.joins:
            query = query.switch(self.model)
            for join in subjoins:
                if join in joined:
                    query = query.switch(join)
                else:
                    query = query.join(join)
                    joined.add(join)

        query = query.group_by(*self.group_by_fields)

        if self.selector:
            query = query.order_by(self.selector)

        return query.dicts()


class StatsMixin(object):
    """ Mixin for resources that provides endpoints for aggregations and stats. """

    aggregate = "id"

    aggregator = "Count"

    binsize = None

    timefield = "created_at"

    timezone = "UTC"

    def get_urls(self):
        return super().get_urls() + (
            ("/stats/", self.protect(self.stats_all, ["GET"])),
            ("/stats/<path:group_by>/", self.protect(self.stats, ["GET"])),
            ("/keys/<field>", self.protect(self.jsonb_keys, ["GET"])),
        )

    def jsonb_keys(self, field):
        field, lookups = StatsQueryBuilder.parse_json_field(field)
        model_attr = getattr(self.model, field)

        for lookup in lookups:
            model_attr = model_attr[lookup]

        if hasattr(model_attr, "as_json"):
            json_lookup = model_attr.as_json()
        else:
            json_lookup = model_attr

        query = self.model.select(fn.DISTINCT(fn.jsonb_object_keys(json_lookup)).alias('key'))

        try:
            keys = [row["key"] for row in query.dicts()]
        except (DataError, ProgrammingError):
            keys = []

        return self.response({"keys": keys})

    def stats_all(self):
        return self.stats()

    def stats(self, group_by=None):
        group_by = group_by.split("/") if group_by else []
        binsize = request.args.get("binsize", self.binsize)
        timefield = request.args.get("timefield", self.timefield)
        timezone = request.args.get("timezone", self.timezone)

        aggregators = request.args.getlist("aggregator")
        aggregates = request.args.getlist("aggregate")

        if not len(aggregates):
            aggregates = [self.aggregate]

        if not len(aggregators):
            aggregators = [self.aggregator]

        builder = StatsQueryBuilder(self.model)

        if binsize and timefield:
            builder.process_timefields(binsize, timefield, timezone)

        for aggregator, aggregate_fieldname in zip(aggregators, aggregates):
            builder.process_aggregator(aggregator, aggregate_fieldname)

        for g in group_by:
            builder.process_group_by(g)

        query = builder.build()
        query = self.process_query(query)

        if "limit" in request.args:
            query = query.limit(request.args.get("limit"))

        aliases = builder.aliases
        meta = dict(aliases=aliases)
        if binsize:
            meta.update(binsize=binsize)

        fmt = request.args.get("format")
        objects = [self.prepare_stats_data(r, timefield, group_by, aliases, fmt) for r in query]
        return self.stats_response(meta, objects, fmt)

    def stats_response(self, meta, objects, response_format="json"):
        if response_format == "csv":
            return self.export_csv(meta, objects)
        return self.response({"meta": meta, "objects": objects})

    def export_csv(self, meta, objects):
        csvdata = StringIO.StringIO()
        if len(objects):
            aliases = meta["aliases"]
            colfields = sorted((col for col in objects[0].keys() if col not in aliases))
            colfields.extend(aliases)
            w = csv.DictWriter(csvdata, colfields)
            w.writerow(dict((c, c) for c in colfields))
            w.writerows(objects)
        return self.response_export(csvdata.getvalue(), 'export.csv', 'text/csv')

    def prepare_stats_data(self, row, timefield, group_by, aliases, response_format="json"):
        datum = {alias: row[alias] for alias in aliases}

        if "id" in row:
            datum["id"] = row["id"]

        if timefield in row:
            timezone = pytz.timezone(request.args.get("timezone", self.timezone))
            dt = row[timefield].astimezone(timezone)
            datum[timefield] = self.get_serializer().convert_value(dt, response_format)

        for g in group_by:
            field = g.rsplit('__')[-1]
            datum[field] = str(row[field])

        return datum


class StatsResource(StatsMixin, RestResource):
    pass
