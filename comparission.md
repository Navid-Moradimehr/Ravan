هسته اصلی
کلاسترهای مدیریت‌شده Kafka / Redpanda
01 / 10
Provision و عملیات کلاسترهای Production-grade با KRaft، بدون ZooKeeper و با rolling upgrade بدون قطعی.

کلاسترها روی Kubernetes با Strimzi یا VM با Ansible مستقر می‌شوند. مدیریت تنظیمات کلاستر — replication factor، min.insync.replicas، rack-awareness، unclean leader election — از طریق کنسول مرکزی و GitOps انجام می‌شود. Rolling upgrade، disk rebalance و broker replacement بدون قطعی consumerها پشتیبانی می‌شود.

نکات کلیدی
Apache Kafka 3.7 با KRaft یا Redpanda 24.x
Rack-aware placement روی چند DC
Rolling upgrade بدون downtime
Auto-healing با Strimzi Operator




Stream Processing
Apache Flink و ksqlDB مدیریت‌شده
02 / 10
Stream Processing Stateful با Flink و SQL روی stream با ksqlDB — برای تیم‌های مهندسی و تحلیل‌گر.

JobManager و TaskManagerهای Flink به‌صورت HA با Checkpoint روی Object Storage بومی پیکربندی می‌شوند. Savepoint برای upgrade بدون از دست رفتن state، RocksDB State Backend برای stateهای بزرگ و Event-Time Windowing با Watermark دقیق پشتیبانی می‌شود. ksqlDB برای تیم‌های BI و تحلیل‌گر، SQL آشنا روی topicهای Kafka را فراهم می‌کند.

نکات کلیدی
Apache Flink 1.19 با Exactly-Once Checkpoint
RocksDB State Backend با Incremental Checkpoint
Event-Time Windowing با Watermark دقیق
ksqlDB برای join، aggregate و materialized view





Kafka Connect با ۸۰+ Connector
03 / 10
Source و Sink Connector آماده برای دیتابیس‌ها، Object Storage، Elasticsearch، Lakehouse و سامانه‌های بومی.

خوشه Kafka Connect به‌صورت Distributed با rebalance خودکار اجرا می‌شود. Connectorهای رسمی Confluent، Debezium و توسعه‌یافته توسط تیم ما برای سامانه‌های ایرانی (همکاران سیستم، چارگون، Core Banking داخلی) در دسترس‌اند. SMT (Single Message Transform) برای فیلتر، route و مخفی‌سازی فیلدهای حساس به‌صورت native پشتیبانی می‌شود.

نکات کلیدی
Debezium برای PostgreSQL، Oracle، MySQL، SQL Server
Sink به S3-compatible، HDFS، Iceberg، Delta Lake
Connector به Elasticsearch، ClickHouse، GITA SIEM
SMT برای masking و routing پویا



Change Data Capture با Debezium
04 / 10
همگام‌سازی پیوسته از Oracle، PostgreSQL و MySQL بدون فشار روی Core سازمان.

Debezium به redo log یا WAL متصل می‌شود — نه به جدول. این یعنی هیچ بار اضافه‌ای روی Core نمی‌آید و تمام تغییرات (INSERT/UPDATE/DELETE) با ترتیب دقیق و بدون از دست رفتن منتقل می‌شوند. Snapshot اولیه به‌صورت Incremental بدون قفل جدول و در زمان Production انجام می‌شود.

نکات کلیدی
اتصال به Oracle LogMiner و XStream
PostgreSQL با Logical Replication و pgoutput
Incremental Snapshot بدون قفل
Schema change tracking و propagation خودکار



Broker MQTT و Bridge به Kafka
05 / 10
Broker MQTT 5.0 برای میلیون‌ها دستگاه IoT با bridge ساختاریافته به topicهای Kafka.

Broker MQTT با پشتیبانی QoS 0/1/2، retained messages، Last Will و sharedSubscription طراحی شده و تا ۲ میلیون اتصال هم‌زمان روی هر node را تحمل می‌کند. Bridge به Kafka با حفظ Device ID به‌عنوان key، تضمین ordering per-device و تبدیل payload به Avro یا Protobuf فراهم است.

نکات کلیدی
MQTT 5.0 با QoS 0/1/2 و retained
تا ۲ میلیون اتصال هم‌زمان per-node
Bridge MQTT → Kafka با partition per-device
TLS و X.509 client certificate برای دستگاه‌ها



Exactly-Once End-to-End
06 / 10
از Producer تا Sink، تضمین حذف تکرار و از دست نرفتن — حتی در failover.

Producer با enable.idempotence و transactional.id، Brokerها با min.insync.replicas، Flink با two-phase commit و Sink Connectorهای transactional همگی هماهنگ پیکربندی می‌شوند تا exactly-once در سطح end-to-end تضمین شود. این برای سناریوهای مالی و billing حیاتی است.

نکات کلیدی
Idempotent Producer به‌صورت پیش‌فرض
Transactional Sink برای DB و Object Storage
Flink Two-Phase Commit با Checkpoint
تست chaos برای تأیید تضمین در failover



مانیتورینگ Lag و سلامت کلاستر
07 / 10
Burrow، Cruise Control، Prometheus و Grafana — همه آماده، با داشبوردهای فارسی.

Consumer lag به‌صورت لحظه‌ای رصد می‌شود و alertها بر اساس threshold یا anomaly فعال می‌شوند. Cruise Control برای auto-rebalance partitionها و حذف hot-brokerها به‌کار می‌رود. تمام متریک‌ها به Prometheus صادر می‌شوند و داشبوردهای آماده Grafana برای SRE تیم شما در دسترس است.

نکات کلیدی
Burrow برای consumer lag دقیق
Cruise Control برای rebalance خودکار
Prometheus exporter روی Broker و Connect
Alert به Slack، Mattermost، GITA SIEM



Tiered Storage و Retention طولانی‌مدت
08 / 10
داده داغ روی SSD، داده سرد روی Object Storage بومی — retention چندماهه بدون انفجار هزینه.

با فعال‌سازی Tiered Storage، segmentهای قدیمی به Object Storage S3-compatible منتقل می‌شوند در حالی که consumerها بدون تغییر قادر به replay از offsetهای قدیمی هستند. این امکان retention چندماهه برای audit، replay و backfill را با هزینه قابل قبول فراهم می‌کند.

نکات کلیدی
S3-compatible Object Storage بومی
Replay از هر offset یا timestamp
رمزنگاری AES-256 در حالت rest
Lifecycle policy قابل تنظیم per-topic



Multi-Region Replication با MirrorMaker 2
09 / 10
تکرار فعال-فعال یا فعال-منفعل بین DCها، با حفظ offset و consumer group.

MirrorMaker 2 با topology قابل تنظیم بین DCها مستقر می‌شود. offset translation برای failover بدون از دست رفتن موقعیت consumer، RemoteTopicها با prefix شفاف و alias مدیریت‌شده، و DR Drill دوره‌ای برای تأیید SLA. این برای سازمان‌های با الزام Geo-Redundancy حیاتی است.

نکات کلیدی
Topology Active-Active یا Active-Passive
Offset translation برای failover
Latency replication زیر ۲ ثانیه روی WAN داخلی
DR Drill خودکار و گزارش انطباق



Schema Registry و Evolution امن
10 / 10
Avro، Protobuf و JSON Schema با اعمال سازگاری backward / forward / full.

هر topic به یک subject در Schema Registry متصل است و هر schema جدید قبل از register شدن از نظر سازگاری چک می‌شود. این جلوی شکستن مصرف‌کننده‌ها در deploy جدید را می‌گیرد. SDKهای Producer/Consumer به‌صورت native با Registry یکپارچه‌اند و serialization بهینه را تأمین می‌کنند.

نکات کلیدی
پشتیبانی Avro، Protobuf و JSON Schema
Compatibility mode قابل تنظیم per-subject
Versioning و رولبک schema
یکپارچگی با Kafka Connect و Flink
