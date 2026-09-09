-- Skillected Jobs — Migration 003: reference data (roles, domains, skill taxonomy, settings).

INSERT OR IGNORE INTO roles (name, description) VALUES
    ('admin', 'Full platform administration'),
    ('placement_officer', 'Placement intelligence and candidate support'),
    ('viewer', 'Read-only internal access');

INSERT OR IGNORE INTO domains (name, slug, icon, description, sort_order) VALUES
    ('Full Stack Development', 'full-stack', '💻', 'Full Stack Developer, Software Developer, Software Engineer, Frontend, Backend, Web, React, Node.js, Java, Spring Boot, Python, Django, MERN, JavaScript, TypeScript', 10),
    ('Data Science & AI/ML', 'data-science-ai-ml', '🤖', 'Data Scientist, Machine Learning Engineer, AI Engineer, Generative AI, Agentic AI, NLP, Computer Vision, Deep Learning, MLOps, AI Research', 20),
    ('Data Analytics', 'data-analytics', '📊', 'Data Analyst, BI Analyst, Business Intelligence, Reporting Analyst, SQL, Power BI, Tableau, Excel, Data Visualization, ETL', 30),
    ('Business Analysis', 'business-analysis', '🧭', 'Business Analyst, IT Business Analyst, Functional Analyst, Product Analyst, Process Analyst, Requirements Analyst', 40),
    ('DevOps & Cloud', 'devops-cloud', '☁️', 'DevOps Engineer, Cloud Engineer, AWS, Azure, GCP, Kubernetes, Docker, Terraform, Jenkins, CI/CD, SRE, Platform Engineer, Cloud Support', 50),
    ('Cybersecurity', 'cybersecurity', '🛡', 'SOC Analyst, Security Analyst, Security Engineer, VAPT, Penetration Testing, Ethical Hacking, AppSec, Cloud Security, Incident Response, Forensics, GRC, SIEM', 60),
    ('Embedded Systems & IoT', 'embedded-iot', '🔌', 'Embedded Engineer, Firmware Engineer, IoT Engineer, Embedded C/C++, ARM, STM32, RTOS, Embedded Linux, Automotive Embedded', 70),
    ('QA & Testing', 'qa-testing', '🧪', 'QA Engineer, Software Tester, Automation Tester, SDET, Selenium, Playwright, Cypress, API Testing, Manual Testing', 80),
    ('Other IT', 'other-it', '🧩', 'Mobile, DevSecOps, DBA, Network Engineering, IT Support, System Administration, Product Management, UI/UX, SAP, Salesforce, ServiceNow, RPA, Blockchain, Game Development, Technical Writing', 90);

INSERT OR IGNORE INTO site_settings (key, value) VALUES
    ('auto_publish_threshold', '85'),
    ('manual_review_threshold', '70'),
    ('crawl_frequency_minutes', '720'),
    ('poster_generation', 'on'),
    ('whatsapp_generation', 'on'),
    ('candidate_notifications', 'on'),
    ('resume_matching', 'off'),
    ('job_alerts', 'on');

INSERT OR IGNORE INTO skill_taxonomy (canonical, category, is_technology) VALUES
    ('JavaScript','language',1),('TypeScript','language',1),('Python','language',1),
    ('Java','language',1),('C','language',1),('C++','language',1),('C#','language',1),
    ('Go','language',1),('Kotlin','language',1),('Swift','language',1),('SQL','language',1),
    ('Bash','language',1),('R','language',1),('Scala','language',1),('PHP','language',1),
    ('React','framework',1),('Next.js','framework',1),('Angular','framework',1),('Vue.js','framework',1),
    ('Node.js','framework',1),('Express.js','framework',1),('Django','framework',1),('Flask','framework',1),
    ('Spring Boot','framework',1),('FastAPI','framework',1),('.NET','framework',1),('React Native','framework',1),
    ('Flutter','framework',1),('Android','platform',1),('iOS','platform',1),
    ('HTML','markup',1),('CSS','markup',1),('SASS','markup',1),('Tailwind CSS','framework',1),
    ('AWS','cloud',1),('Azure','cloud',1),('GCP','cloud',1),('Kubernetes','devops',1),('Docker','devops',1),
    ('Terraform','devops',1),('Ansible','devops',1),('Jenkins','devops',1),('GitHub Actions','devops',1),
    ('GitLab CI/CD','devops',1),('CI/CD','devops',1),('Linux','os',1),('Shell Scripting','devops',1),
    ('Git','tool',1),('GitHub','tool',1),('Postman','tool',1),('JIRA','tool',1),('Confluence','tool',1),
    ('MySQL','database',1),('PostgreSQL','database',1),('MongoDB','database',1),('Redis','database',1),
    ('Oracle DB','database',1),('SQL Server','database',1),('Elasticsearch','database',1),
    ('Apache Kafka','data',1),('Apache Spark','data',1),('Apache Airflow','data',1),('Snowflake','data',1),
    ('ETL','data',0),('Data Warehousing','data',0),('Data Modeling','data',0),
    ('Power BI','analytics',1),('Tableau','analytics',1),('Excel','analytics',1),('Looker','analytics',1),
    ('Data Visualization','analytics',0),('Reporting','analytics',0),('Dashboarding','analytics',0),
    ('Pandas','library',1),('NumPy','library',1),('scikit-learn','library',1),('TensorFlow','library',1),
    ('PyTorch','library',1),('Keras','library',1),('OpenCV','library',1),('spaCy','library',1),('NLTK','library',1),
    ('Hugging Face','library',1),('LangChain','library',1),('Generative AI','ai',0),('LLMs','ai',0),
    ('Prompt Engineering','ai',0),('NLP','ai',0),('Computer Vision','ai',0),('Deep Learning','ai',0),
    ('Reinforcement Learning','ai',0),('Agentic AI','ai',0),('RAG','ai',0),('MLOps','ai',0),
    ('Machine Learning','ai',0),('Statistics','analytics',0),('A/B Testing','analytics',0),
    ('Selenium','testing',1),('Playwright','testing',1),('Cypress','testing',1),('Pytest','testing',1),
    ('JUnit','testing',1),('TestNG','testing',1),('Appium','testing',1),('API Testing','testing',0),
    ('Manual Testing','testing',0),('Automation Testing','testing',0),('Performance Testing','testing',0),
    ('Embedded C','embedded',1),('Embedded C++','embedded',1),('ARM','embedded',1),('STM32','embedded',1),
    ('RTOS','embedded',1),('Embedded Linux','embedded',1),('AUTOSAR','embedded',1),('CAN Bus','embedded',1),
    ('IoT','embedded',0),('MQTT','embedded',1),('Microcontrollers','embedded',0),('Yocto','embedded',1),
    ('SIEM','security',1),('Splunk','security',1),('QRadar','security',1),('CrowdStrike','security',1),
    ('VAPT','security',0),('Penetration Testing','security',0),('Ethical Hacking','security',0),
    ('Burp Suite','security',1),('Metasploit','security',1),('Nmap','security',1),('Wireshark','security',1),
    ('OWASP','security',0),('Application Security','security',0),('Cloud Security','security',0),
    ('Network Security','security',0),('Incident Response','security',0),('Digital Forensics','security',0),
    ('GRC','security',0),('ISO 27001','security',0),('SOC Operations','security',0),('Firewalls','security',1),
    ('IDS/IPS','security',1),('VPN','security',1),('IAM','security',0),('Zero Trust','security',0),
    ('TCP/IP','network',0),('DNS','network',0),('BGP','network',0),('Routing & Switching','network',0),
    ('CCNA','network',0),('Cisco','network',1),('Load Balancing','network',0),
    ('SAP','erp',1),('SAP ABAP','erp',1),('Salesforce','erp',1),('ServiceNow','erp',1),
    ('PowerApps','erp',1),('SharePoint','erp',1),('RPA','automation',0),('UiPath','automation',1),
    ('Automation Anywhere','automation',1),('Blue Prism','automation',1),
    ('Solidity','blockchain',1),('Ethereum','blockchain',1),('Smart Contracts','blockchain',0),
    ('Unity','gamedev',1),('Unreal Engine','gamedev',1),('Blender','gamedev',1),
    ('Figma','design',1),('Adobe XD','design',1),('UI Design','design',0),('UX Research','design',0),
    ('Wireframing','design',0),('Prototyping','design',0),('Design Systems','design',0),
    ('Requirements Gathering','ba',0),('Process Mapping','ba',0),('User Stories','ba',0),
    ('Stakeholder Management','ba',0),('Agile','method',0),('Scrum','method',0),('Kanban','method',0),
    ('SDLC','method',0),('Technical Writing','soft',0),('Documentation','soft',0),
    ('REST APIs','api',0),('GraphQL','api',1),('gRPC','api',1),('Microservices','arch',0),
    ('System Design','arch',0),('Data Structures','cs',0),('Algorithms','cs',0),
    ('Communication','soft',0),('Problem Solving','soft',0),('Leadership','soft',0);

INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'ReactJS', 'reactjs' FROM skill_taxonomy WHERE canonical='React';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'React.js', 'react.js' FROM skill_taxonomy WHERE canonical='React';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'React JS', 'react js' FROM skill_taxonomy WHERE canonical='React';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'NodeJS', 'nodejs' FROM skill_taxonomy WHERE canonical='Node.js';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'Node', 'node' FROM skill_taxonomy WHERE canonical='Node.js';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'JS', 'js' FROM skill_taxonomy WHERE canonical='JavaScript';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'TS', 'ts' FROM skill_taxonomy WHERE canonical='TypeScript';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'K8s', 'k8s' FROM skill_taxonomy WHERE canonical='Kubernetes';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'Amazon Web Services', 'amazon web services' FROM skill_taxonomy WHERE canonical='AWS';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'MS SQL', 'ms sql' FROM skill_taxonomy WHERE canonical='SQL Server';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'MSSQL', 'mssql' FROM skill_taxonomy WHERE canonical='SQL Server';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'Postgres', 'postgres' FROM skill_taxonomy WHERE canonical='PostgreSQL';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'ML', 'ml' FROM skill_taxonomy WHERE canonical='Machine Learning';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'AI', 'ai' FROM skill_taxonomy WHERE canonical='Machine Learning';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'Pen Testing', 'pen testing' FROM skill_taxonomy WHERE canonical='Penetration Testing';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'Pentest', 'pentest' FROM skill_taxonomy WHERE canonical='Penetration Testing';
INSERT OR IGNORE INTO skill_aliases (skill_id, alias, alias_lower)
SELECT skill_id, 'Information Security', 'information security' FROM skill_taxonomy WHERE canonical='Cybersecurity'
   AND (SELECT COUNT(*) FROM skill_taxonomy WHERE canonical='Cybersecurity') > 0;
