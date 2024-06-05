create database if not exists depi;

use depi;

create table if not exists resource_group (
  tool_id varchar(32) not null,
  url varchar(512) not null,
  name varchar(100),
  version varchar(100),
  primary key (tool_id, url)
);

create table if not exists resource (
  tool_id varchar(32) not null,
  rg_url varchar(512) not null,
  url varchar(512) not null,
  id varchar(512) not null,
  name varchar(100),
  deleted boolean,
  primary key (tool_id, rg_url, url)
);

create table if not exists link (
  from_tool_id varchar(32) not null,
  from_rg_url varchar(512) not null,
  from_url varchar(512) not null,
  to_tool_id varchar(32) not null,
  to_rg_url varchar(512) not null,
  to_url varchar(512) not null,
  deleted boolean,
  dirty boolean,
  last_clean_version varchar(100),
  primary key (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url)
);

create table if not exists inferred_dirtiness (
  from_tool_id varchar(32) not null,
  from_rg_url varchar(512) not null,
  from_url varchar(512) not null,
  to_tool_id varchar(32) not null,
  to_rg_url varchar(512) not null,
  to_url varchar(512) not null,
  source_tool_id varchar(32) not null,
  source_rg_url varchar(512) not null,
  source_url varchar(512) not null,
  source_last_clean_version varchar(100),
  primary key (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url, source_tool_id,
      source_rg_url, source_url)
);

create user if not exists depiadmin identified by 'DEPIADMIN_PASSWORD';
grant all on *.* to 'depiadmin'@'localhost';
flush privileges;

create user if not exists depi identified by 'DEPI_PASSWORD';
grant all on depi.* to 'depi'@'localhost';
flush privileges;

call DOLT_COMMIT('-A', '-m', 'Initial commit', '--author', 'Your Name <your.name@your.org>');
