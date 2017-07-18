-- Definition of tables for Supply Chain DB
-- Tables to create


CREATE TABLE block (
	block_id			char(128) primary key,		-- primary key
	block_num			integer, 
	state_root_hash		char(64)
);


CREATE TABLE record (
	id 					bigserial primary key, 		-- primary key
	start_block_num		integer, 		-- This field is populated in response to events from the State Delta Subscription service, but is loosely coupled to the block_history table.
	end_block_num		integer, 		-- This field is populated in response to events from the State Delta Subscription service, but is loosely coupled to the block_history table.
	identifier			varchar(128), 	-- The natural key of the record, serial number of attached sensor identifier.
	creation_time		bigint,			-- The time the record was created
	finalized			boolean			-- Is the record finalized?
);


CREATE TABLE agent(
	id 					bigserial primary key,		-- primary key
	start_block_num		integer, 		-- This field is populated in response to events from the State Delta Subscription service, but is loosely coupled to the block_history table.
	end_block_num		integer, 		-- This field is populated in response to events from the State Delta Subscription service, but is loosely coupled to the block_history table.
	identifier 			varchar(128),	-- Hex-encoded public key of agent
	name				text			-- The agent name
);

CREATE TABLE type_enum(
	id 					integer primary key, 		-- primary key
	name				char(12), 		-- OWNER, CUSTODIAN
	code  				smallint		-- 0, 1
);


CREATE TABLE status_enum(
	id 					integer primary key, 		--- primary key
	name				char(12),		-- OPEN, CANCELED, REJECTED, ACCEPTED
	code 				smallint 		-- 0, 1, 2, 3		
);

CREATE TABLE record_agent(
	id 					bigserial primary key, 						-- primary key
	record_id			bigserial references record(id),	-- Foreign key from record/id
	agent_identifier	varchar(128),					-- This field is loosely coupled to agent/identifier
	start_time			bigint,
	agent_type			integer	 references type_enum(id)	-- Fore\ign key from type_enum/id
);


CREATE TABLE application(
	id 					bigserial primary key, 		-- primary key
	start_block_num		integer, 		-- This field is populated in response to events from the State Delta Subscription service, but is loosely coupled to the block_history table.
	end_block_num		integer, 		-- This field is populated in response to events from the State Delta Subscription service, but is loosely coupled to the block_history table.
	record_identifier	varchar(128),	-- Loosely coupled record/identifier
	applicant 			varchar(128),			-- Public key of the applicant
	creation_time		bigint,
	type 				integer references type_enum(id),		-- Foreign key from type_enum/id
	status 				integer references status_enum(id),		-- Foreign key from status_enum/id
	terms				text
);





-- SAMPLE DATA BELOW

INSERT INTO type_enum VALUES(1, 'OWNER', 1), (2, 'CUSTODIAN', 2);

INSERT INTO status_enum VALUES(1, 'OPEN', 1), (2, 'CANCELED', 2), (3, 'REJECTED', 3), (4, 'ACCEPTED', 4);

INSERT INTO block VALUES('1', 1, 'A1B1C1D1E1'), ('2', 2, 'KFJAKDFJKADSFJASDKFJ');

INSERT INTO record VALUES(1, 1, NULL, 'TRACKING_NO_1', 1498592241, false);
INSERT INTO record VALUES(2, 2, NULL, 'TRACKING_NO_2', 1498592245, true);

INSERT INTO agent VALUES(1, 1, NULL, 'laksdflkkajdkfadj1d22', 'Todd Ojala');
INSERT INTO agent VALUES(2, 2, NULL, '111sdflkkajdkfadj1d22', 'Sue Ellen');
INSERT INTO agent VALUES(3, 2, NULL, '1110003F330D0D0D0DDDD', 'Man Ray');
INSERT INTO agent VALUES(4, 3, NULL, '1110003F330D0D0D0DDD1', 'Man Ray0');
INSERT INTO agent VALUES(5, 3, NULL, '1110003F330D0D0D0DDD2', 'Man Ray1');
INSERT INTO agent VALUES(6, 4, NULL, '1110003F330D0D0D0DDD3', 'Man Ray2');
INSERT INTO agent VALUES(7, 5, NULL, '1110003F330D0D0D0DDD4', 'Man Ray3');
INSERT INTO agent VALUES(8, 5, NULL, '1110003F330D0D0D0DDD5', 'Man Ray4');
INSERT INTO agent VALUES(9, 6, NULL, '1110003F330D0D0D0DDD6', 'Man Ray5');
INSERT INTO agent VALUES(10, 6, NULL, '1110003F330D0D0D0DDD7', 'Man Ray6');

INSERT INTO record_agent VALUES(1, 1, 'laksdflkkajdkfadj1d22', 1498592241, 1);
INSERT INTO record_agent VALUES(2, 1, '111sdflkkajdkfadj1d22', 1498592242, 2);
INSERT INTO record_agent VALUES(3, 2, '111sdflkkajdkfadj1d22', 1498592243, 1);
INSERT INTO record_agent VALUES(4, 1, '1110003F330D0D0D0DDDD', 1498992243, 1);

INSERT INTO application	VALUES(1, 1, NULL, 'TRACKING_NO_1', 'Joe Johnson', 1498592882, 2, 1, 'COD');
INSERT INTO application	VALUES(2, 2, NULL, 'TRACKING_NO_1', '111sdflkkajdkfadj1d22', 1498592882, 1, 2, 'COD');




